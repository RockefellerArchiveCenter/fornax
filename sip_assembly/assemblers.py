import logging
from os.path import isdir
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


class SIPAssembler(object):
    """Creates an Archivematica-compliant SIP."""
    def __init__(self, dirs=None):
        self.upload_dir = dirs['upload'] if dirs else settings.UPLOAD_DIR
        self.processing_dir = dirs['processing'] if dirs else settings.PROCESSING_DIR
        self.storage_dir = dirs['storage'] if dirs else settings.STORAGE_DIR
        for dir in [self.upload_dir, self.processing_dir, self.storage_dir]:
            if not isdir(dir):
                raise SIPAssemblyError("Directory {} does not exist".format(dir))

    def run(self):
        self.log = logger.new(request_id=str(uuid4()))
        self.log.debug("Found {} SIPs to process".format(len(SIP.objects.filter(process_status=SIP.CREATED))))
        sip_count = 0
        for sip in SIP.objects.filter(process_status=SIP.CREATED):
            self.log = logger.bind(object=sip)
            try:
                library.move_to_directory(sip, self.processing_dir)
                library.extract_all(sip, self.processing_dir)
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
                library.add_processing_config(sip)
                library.update_manifests(sip)
                library.create_package(sip)
            except Exception as e:
                raise SIPAssemblyError("Error updating SIP contents: {}".format(e))

            try:
                library.move_to_directory(sip, self.storage_dir)
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
                raise SIPAssemblyError("Error starting transfer in Archivematica: {}".format(e))
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
                raise SIPAssemblyError("Error approving transfer in Archivematica: {}".format(e))
        else:
            return "No transfers to approve."
