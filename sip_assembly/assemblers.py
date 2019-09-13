import json
from os import remove
from os.path import isdir, isfile, join
import requests

from fornax import settings
from sip_assembly import library
from .clients import ArchivematicaClient
from .models import SIP


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
                raise SIPAssemblyError("Directory does not exist", dir)
        try:
            self.processing_config = ArchivematicaClient(
                settings.ARCHIVEMATICA['username'],
                settings.ARCHIVEMATICA['api_key'],
                settings.ARCHIVEMATICA['baseurl'],
                settings.ARCHIVEMATICA['location_uuid']).retrieve(
                    'processing-configuration/{}/'.format(
                        settings.ARCHIVEMATICA['processing_config']))
        except requests.exceptions.ConnectionError as e:
            raise SIPAssemblyError("Cannot connect to Archivematica: {}".format(e), None)

    def run(self):
        sip_ids = []
        for sip in SIP.objects.filter(process_status=SIP.CREATED):
            try:
                library.copy_to_directory(sip, self.tmp_dir)
                library.extract_all(sip, self.tmp_dir)
                library.validate(sip)
            except Exception as e:
                raise SIPAssemblyError("Error moving SIP to processing directory: {}".format(e), sip.bag_identifier)

            try:
                library.move_objects_dir(sip)
                library.create_structure(sip)
            except Exception as e:
                raise SIPAssemblyError("Error restructuring SIP: {}".format(e), sip.bag_identifier)

            if sip.data['rights_statements']:
                try:
                    library.create_rights_csv(sip)
                    library.validate_rights_csv(sip)
                except Exception as e:
                    raise SIPAssemblyError("Error creating rights.csv: {}".format(e), sip.bag_identifier)

            try:
                library.update_bag_info(sip)
                library.add_processing_config(sip, self.processing_config)
                library.update_manifests(sip)
                library.create_package(sip)
            except Exception as e:
                raise SIPAssemblyError("Error updating SIP contents: {}".format(e), sip.bag_identifier)

            try:
                library.move_to_directory(sip, self.dest_dir)
                sip.process_status = SIP.ASSEMBLED
                sip.save()
            except Exception as e:
                raise SIPAssemblyError("Error delivering SIP to Archivematica: {}".format(e), sip.bag_identifier)

        return ("All SIPs assembled.", sip_ids)


class SIPActions(object):
    def __init__(self):
        self.client = ArchivematicaClient(settings.ARCHIVEMATICA['username'],
                                          settings.ARCHIVEMATICA['api_key'],
                                          settings.ARCHIVEMATICA['baseurl'],
                                          settings.ARCHIVEMATICA['location_uuid'])
        if not self.client:
            raise SIPAssemblyError("Cannot connect to Archivematica", None)

    def start_transfer(self):
        """Starts transfer in Archivematica by sending a POST request to the
           /transfer/start_transfer/ endpoint."""
        if len(SIP.objects.filter(process_status=SIP.ASSEMBLED)):
            try:
                sip = SIP.objects.filter(process_status=SIP.ASSEMBLED)[0]
                self.client.send_start_transfer_request(sip)
                sip.process_status = SIP.STARTED
                sip.save()
                return ("SIP started.", [sip.bag_identifier])
            except Exception as e:
                raise SIPActionError("Error starting transfer in Archivematica: {}".format(e), sip.bag_identifier)
        else:
            return ("No transfers to start.", None)

    def approve_transfer(self):
        """Starts transfer in Archivematica by sending a POST request to the
           /transfer/approve_transfer/ endpoint."""
        if len(SIP.objects.filter(process_status=SIP.STARTED)):
            try:
                sip = SIP.objects.filter(process_status=SIP.STARTED)[0]
                self.client.send_approve_transfer_request(sip)
                sip.process_status = SIP.APPROVED
                sip.save()
                return ("SIP approved.", [sip.bag_identifier])
            except Exception as e:
                raise SIPActionError("Error approving transfer in Archivematica: {}".format(e), sip.bag_identifier)
        else:
            return ("No transfers to approve.", None)

    def remove_completed_transfers(self):
        """Removes completed transfers from Archivematica dashboard."""
        try:
            completed = self.client.cleanup('transfer')
            return ("All completed transfers removed from dashboard", completed)
        except Exception as e:
            raise SIPActionError("Error removing transfer from Archivematica dashboard", e)

    def remove_completed_ingests(self):
        """Removes completed transfers from Archivematica dashboard."""
        try:
            completed = self.client.cleanup('ingest')
            return ("All completed ingests removed from dashboard", completed)
        except Exception as e:
            raise SIPActionError("Error removing ingests from Archivematica dashboard", e)


class CleanupRequester:
    def __init__(self, url):
        self.url = url

    def run(self):
        sip_ids = []
        for sip in SIP.objects.filter(process_status=SIP.APPROVED):
            r = requests.post(
                self.url,
                data=json.dumps({"identifier": sip.bag_identifier}),
                headers={"Content-Type": "application/json"},
            )
            if r.status_code != 200:
                raise CleanupError(r.reason, sip.bag_identifier)
            sip.process_status = SIP.CLEANED_UP
            sip.save()
        return ("Requests sent to cleanup SIPs.", sip_ids)


class CleanupRoutine:
    def __init__(self, identifier, dirs):
        self.identifier = identifier
        self.dest_dir = dirs['dest'] if dirs else settings.DEST_DIR
        if not self.identifier:
            raise CleanupError("No identifier submitted, unable to perform CleanupRoutine.", None)

    def run(self):
        try:
            self.filepath = "{}.tar.gz".format(join(self.dest_dir, self.identifier))
            if isfile(self.filepath):
                remove(self.filepath)
                return ("Transfer removed.", self.identifier)
            return ("Transfer was not found.", self.identifier)
        except Exception as e:
            raise CleanupError(e, self.identifier)
