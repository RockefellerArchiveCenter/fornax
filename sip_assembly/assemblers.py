import json
from os import remove
from os.path import isdir, isfile, join

from amclient import AMClient, errors
import requests

from fornax import settings
from sip_assembly import library
from .models import SIP


class SIPAssemblyError(Exception): pass
class SIPActionError(Exception): pass
class CleanupError(Exception): pass


class ArchivematicaRoutine:

    """Base class which instantiates an Archivematica client"""
    def __init__(self):
        self.client = AMClient(
            am_api_key=settings.ARCHIVEMATICA['api_key'],
            am_user_name=settings.ARCHIVEMATICA['username'],
            am_url=settings.ARCHIVEMATICA['baseurl'],
            transfer_source=settings.ARCHIVEMATICA['location_uuid'],
            processing_config=settings.ARCHIVEMATICA['processing_config']
        )
        self.processing_config = self.client.get_processing_config()
        if type(self.processing_config) == int:
            raise SIPAssemblyError(errors.error_lookup(self.processing_config),)


class SIPAssembler(ArchivematicaRoutine):
    """Creates an Archivematica-compliant SIP."""
    def __init__(self, dirs=None):
        super(SIPAssembler, self).__init__()
        self.src_dir = dirs['src'] if dirs else settings.SRC_DIR
        self.tmp_dir = dirs['tmp'] if dirs else settings.TMP_DIR
        self.dest_dir = dirs['dest'] if dirs else settings.DEST_DIR
        for dir in [self.src_dir, self.tmp_dir, self.dest_dir]:
            if not isdir(dir):
                raise SIPAssemblyError("Directory does not exist", dir)

    def run(self):
        sip_ids = []
        for sip in SIP.objects.filter(process_status=SIP.CREATED):
            try:
                library.copy_to_directory(sip, self.tmp_dir)
                library.extract_all(sip, self.tmp_dir)
                library.validate(sip.bag_path)
            except Exception as e:
                raise SIPAssemblyError("Error moving SIP to processing directory: {}".format(e), sip.bag_identifier)

            try:
                library.move_objects_dir(sip.bag_path)
                library.create_structure(sip.bag_path)
            except Exception as e:
                raise SIPAssemblyError("Error restructuring SIP: {}".format(e), sip.bag_identifier)

            if sip.data['rights_statements']:
                try:
                    library.create_rights_csv(sip.bag_path, sip.data.get('rights_statements'))
                    library.validate_rights_csv(sip.bag_path)
                except Exception as e:
                    raise SIPAssemblyError("Error creating rights.csv: {}".format(e), sip.bag_identifier)

            try:
                library.update_bag_info(sip.bag_path, {'Internal-Sender-Identifier': sip.data['identifier']})
                library.add_processing_config(sip.bag_path, self.processing_config)
                library.update_manifests(sip.bag_path)
                library.create_targz_package(sip)
            except Exception as e:
                raise SIPAssemblyError("Error updating SIP contents: {}".format(e), sip.bag_identifier)

            try:
                library.move_to_directory(sip, self.dest_dir)
                sip.process_status = SIP.ASSEMBLED
                sip.save()
            except Exception as e:
                raise SIPAssemblyError("Error delivering SIP to Archivematica transfer source: {}".format(e), sip.bag_identifier)

            sip_ids.append(sip.bag_identifier)

        return "All SIPs assembled.", sip_ids


class SIPActions(ArchivematicaRoutine):
    """Performs various actions against the Archivematica API."""

    def create_package(self):
        """Starts and approves a transfer in Archivematica."""
        msg = "No transfers to start.",
        if len(SIP.objects.filter(process_status=SIP.ASSEMBLED)):
            next_queued = SIP.objects.filter(process_status=SIP.ASSEMBLED).order_by('last_modified')[0]
            last_started = next(iter(SIP.objects.filter(process_status=SIP.APPROVED).order_by('-last_modified')), None)
            if last_started and self.client.get_unit_status(last_started.bag_identifier) == 'PROCESSING':
                msg = "Another transfer is processing, waiting until it finishes.",
            else:
                self.client.transfer_directory = "{}.tar.gz".format(next_queued.bag_identifier)
                self.client.transfer_name = next_queued.bag_identifier
                self.client.transfer_type = 'zipped bag'
                started = self.client.create_package()
                next_queued.process_status = SIP.APPROVED
                next_queued.save()
                msg = "Transfer started", [started.get('id')]
        return msg

    def remove_completed(self, type):
        """Removes completed transfers and ingests from Archivematica dashboard."""
        completed = getattr(self.client, 'close_completed_{}'.format((type)))()
        if completed.get('close_failed'):
            raise SIPActionError("Error removing {} from Archivematica dashboard: {}".format(type, completed['close_failed']))
        else:
            return "All completed {} removed from dashboard".format(type), completed.get('close_succeeded')


class CleanupRequester:
    """
    Requests that cleanup of SIP files in the source directory be performed by
    another service.
    """
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
        message = "Requests sent to clean up SIPs." if len(sip_ids) else "No SIPS to clean up."
        return message, sip_ids


class CleanupRoutine:
    """Removes files in destination directory."""
    def __init__(self, identifier, dirs):
        self.identifier = identifier
        self.dest_dir = dirs['dest'] if dirs else settings.DEST_DIR
        if not self.identifier:
            raise CleanupError("No identifier submitted, unable to perform CleanupRoutine.",)

    def run(self):
        try:
            self.filepath = "{}.tar.gz".format(join(self.dest_dir, self.identifier))
            if isfile(self.filepath):
                remove(self.filepath)
                return "Transfer removed.", self.identifier
            return "Transfer was not found.", self.identifier
        except Exception as e:
            raise CleanupError(e, self.identifier)
