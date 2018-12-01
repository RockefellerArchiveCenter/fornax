import json
import logging
from os import remove
from os.path import isdir, isfile, join
import requests
from structlog import wrap_logger
from uuid import uuid4

from fornax import settings
from sip_assembly import library
from .clients import ArchivematicaClient
from .models import SIP

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger = wrap_logger(logger)


class SIPAssemblyError(Exception): pass
class SIPActionError(Exception): pass
class CleanupError(Exception): pass


class SIPAssembler(object):
    """Creates an Archivematica-compliant SIP."""
    def __init__(self, dirs=None):
        self.src_dir = dirs['src'] if dirs else settings.SRC_DIR
        self.tmp_dir = dirs['tmp'] if dirs else settings.TMP_DIR
        self.dest_dir = dirs['dest'] if dirs else settings.DEST_DIR
        for dir in [self.src_dir, self.tmp_dir, self.dest_dir]:
            if not isdir(dir):
                raise SIPAssemblyError("Directory {} does not exist".format(dir))
        self.client = ArchivematicaClient(settings.ARCHIVEMATICA['username'],
                                          settings.ARCHIVEMATICA['api_key'],
                                          settings.ARCHIVEMATICA['baseurl'],
                                          settings.ARCHIVEMATICA['location_uuid'])
        if not self.client:
            raise SIPAssemblyError("Cannot connect to Archivematica")

    def run(self):
        self.log = logger.new(request_id=str(uuid4()))
        self.log.debug("Found {} SIPs to process".format(len(SIP.objects.filter(process_status=SIP.CREATED))))
        sip_count = 0
        for sip in SIP.objects.filter(process_status=SIP.CREATED):
            self.log = logger.bind(object=sip)
            try:
                library.copy_to_directory(sip, self.tmp_dir)
                library.extract_all(sip, self.tmp_dir)
                library.validate(sip)
            except Exception as e:
                raise SIPAssemblyError("Error moving SIP to processing directory: {}".format(e))

            try:
                library.move_objects_dir(sip)
                library.create_structure(sip)
            except Exception as e:
                raise SIPAssemblyError("Error restructuring SIP: {}".format(e))

            if sip.data['rights_statements']:
                try:
                    library.create_rights_csv(sip)
                    library.validate_rights_csv(sip)
                except Exception as e:
                    raise SIPAssemblyError("Error creating rights.csv: {}".format(e))

            try:
                library.update_bag_info(sip)
                library.add_processing_config(sip, self.client)
                library.update_manifests(sip)
                library.create_package(sip)
            except Exception as e:
                raise SIPAssemblyError("Error updating SIP contents: {}".format(e))

            try:
                library.move_to_directory(sip, self.dest_dir)
                sip.process_status = SIP.ASSEMBLED
                sip.save()
            except Exception as e:
                raise SIPAssemblyError("Error delivering SIP to Archivematica: {}".format(e))

            sip_count += 1

        return "{} SIPs assembled.".format(sip_count)


class SIPActions(object):
    def __init__(self):
        self.client = ArchivematicaClient(settings.ARCHIVEMATICA['username'],
                                          settings.ARCHIVEMATICA['api_key'],
                                          settings.ARCHIVEMATICA['baseurl'],
                                          settings.ARCHIVEMATICA['location_uuid'])
        if not self.client:
            raise SIPAssemblyError("Cannot connect to Archivematica")

    def start_transfer(self):
        """Starts transfer in Archivematica by sending a POST request to the
           /transfer/start_transfer/ endpoint."""
        if len(SIP.objects.filter(process_status=SIP.ASSEMBLED)):
            try:
                sip = SIP.objects.filter(process_status=SIP.ASSEMBLED)[0]
                self.client.send_start_transfer_request(sip)
                sip.process_status = SIP.STARTED
                sip.save()
                return "{} started.".format(sip.bag_identifier)
            except Exception as e:
                raise SIPActionError("Error starting transfer in Archivematica: {}".format(e))
        else:
            return "No transfers to start."

    def approve_transfer(self):
        """Starts transfer in Archivematica by sending a POST request to the
           /transfer/approve_transfer/ endpoint."""
        if len(SIP.objects.filter(process_status=SIP.STARTED)):
            try:
                sip = SIP.objects.filter(process_status=SIP.STARTED)[0]
                self.client.send_approve_transfer_request(sip)
                sip.process_status = SIP.APPROVED
                sip.save()
                return "{} approved.".format(sip.bag_identifier)
            except Exception as e:
                raise SIPActionError("Error approving transfer in Archivematica: {}".format(e))
        else:
            return "No transfers to approve."


class CleanupRequester:
    def __init__(self, url):
        self.url = url

    def run(self):
        sip_count = 0
        for sip in SIP.objects.filter(process_status=SIP.APPROVED):
            r = requests.post(
                self.url,
                data=json.dumps({"identifier": sip.bag_identifier}),
                headers={"Content-Type": "application/json"},
            )
            if r.status_code != 200:
                raise CleanupError(r.status_code, r.reason)
            sip.process_status = SIP.CLEANED_UP
            sip.save()
            sip_count += 1
        return "Requests sent to cleanup {} SIPs.".format(sip_count)


class CleanupRoutine:
    def __init__(self, identifier, dirs):
        self.identifier = identifier
        self.dest_dir = dirs['dest'] if dirs else settings.DEST_DIR

    def run(self):
        try:
            self.filepath = "{}.tar.gz".format(join(self.dest_dir, self.identifier))
            if isfile(self.filepath):
                remove(self.filepath)
                return "Transfer {} removed.".format(self.identifier)
            return "Transfer {} was not found.".format(self.identifier)
        except Exception as e:
            raise CleanupError(e)
