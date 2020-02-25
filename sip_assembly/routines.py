import json
from os import remove
from os.path import isdir, isfile, join

import requests
from amclient import AMClient, errors
from asterism import bagit_helpers
from fornax import settings
from sip_assembly import routines_helpers as helpers

from .models import SIP


class SIPAssemblyError(Exception):
    pass


class SIPActionError(Exception):
    pass


class CleanupError(Exception):
    pass


class ArchivematicaRoutine:
    def get_client(self, origin):
        """Instantiates an Archivematica client based on SIP origin"""
        am_settings = settings.ARCHIVEMATICA[origin]
        return AMClient(
            am_api_key=am_settings['api_key'],
            am_user_name=am_settings['username'],
            am_url=am_settings['baseurl'],
            transfer_source=am_settings['location_uuid'],
            processing_config=am_settings['processing_config']
        )

    def get_processing_config(self, client):
        """Returns a processing configuration file from Archivematica"""
        processing_config = client.get_processing_config()
        if isinstance(processing_config, int):
            raise SIPAssemblyError(errors.error_lookup(processing_config),)
        return processing_config


class SIPAssembler(ArchivematicaRoutine):
    """Creates an Archivematica-compliant SIP."""

    def __init__(self):
        super(SIPAssembler, self).__init__()
        self.src_dir = settings.SRC_DIR
        self.tmp_dir = settings.TMP_DIR
        self.dest_dir = settings.DEST_DIR
        for dir in [self.src_dir, self.tmp_dir, self.dest_dir]:
            if not isdir(dir):
                raise SIPAssemblyError("Directory does not exist", dir)

    def run(self):
        sip_ids = []
        for sip in SIP.objects.filter(process_status=SIP.CREATED):
            client = self.get_client(sip.origin)
            try:
                helpers.copy_to_directory(sip, self.tmp_dir)
                helpers.extract_all(sip, self.tmp_dir)
                bagit_helpers.validate(sip.bag_path)
            except Exception as e:
                raise SIPAssemblyError(
                    "Error moving SIP to processing directory: {}".format(e),
                    sip.bag_identifier)

            try:
                helpers.move_objects_dir(sip.bag_path)
                helpers.create_structure(sip.bag_path)
            except Exception as e:
                raise SIPAssemblyError(
                    "Error restructuring SIP: {}".format(e),
                    sip.bag_identifier)

            if sip.data['rights_statements']:
                try:
                    helpers.create_rights_csv(
                        sip.bag_path, sip.data.get('rights_statements'))
                    helpers.validate_rights_csv(sip.bag_path)
                except Exception as e:
                    raise SIPAssemblyError(
                        "Error creating rights.csv: {}".format(e),
                        sip.bag_identifier)

            try:
                bagit_helpers.update_bag_info(
                    sip.bag_path, {
                        'Internal-Sender-Identifier': sip.bag_identifier})
                helpers.add_processing_config(
                    sip.bag_path, self.get_processing_config(client))
                bagit_helpers.update_manifests(sip.bag_path)
                helpers.create_targz_package(sip)
            except Exception as e:
                raise SIPAssemblyError(
                    "Error updating SIP contents: {}".format(e),
                    sip.bag_identifier)

            try:
                helpers.move_to_directory(sip, self.dest_dir)
                sip.process_status = SIP.ASSEMBLED
                sip.save()
            except Exception as e:
                raise SIPAssemblyError(
                    "Error delivering SIP to Archivematica transfer source: {}".format(
                        e),
                    sip.bag_identifier)

            sip_ids.append(sip.bag_identifier)

        return "All SIPs assembled.", sip_ids


class SIPActions(ArchivematicaRoutine):
    """Performs various actions against the Archivematica API."""

    def create_package(self):
        """Starts and approves a transfer in Archivematica."""
        msg = "No transfers to start.",
        if len(SIP.objects.filter(process_status=SIP.ASSEMBLED)):
            next_queued = SIP.objects.filter(
                process_status=SIP.ASSEMBLED).order_by('last_modified')[0]
            last_started = next(
                iter(
                    SIP.objects.filter(
                        process_status=SIP.APPROVED).order_by('-last_modified')),
                None)
            client = self.get_client(next_queued.origin)
            if last_started and client.get_unit_status(
                    last_started.bag_identifier) == 'PROCESSING':
                msg = "Another transfer is processing, waiting until it finishes.",
            else:
                client.transfer_directory = "{}.tar.gz".format(
                    next_queued.bag_identifier)
                client.transfer_name = next_queued.bag_identifier
                client.transfer_type = 'zipped bag'
                started = client.create_package()
                next_queued.process_status = SIP.APPROVED
                next_queued.save()
                msg = "Transfer started", [started.get('id')]
        return msg

    def remove_completed(self, type):
        """Removes completed transfers and ingests from Archivematica dashboard."""
        all_completed = []
        dashboards = []
        for origin in settings.ARCHIVEMATICA:
            if settings.ARCHIVEMATICA[origin].get("close_completed"):
                client = self.get_client(origin)
                completed = getattr(client,
                                    'close_completed_{}'.format((type)))()
                dashboards.append(origin)
                if completed.get('close_failed'):
                    raise SIPActionError(
                        "Error removing {} from Archivematica dashboard: {}".format(
                            type, completed['close_failed']))
                else:
                    all_completed += completed.get('close_succeeded', [])
        return "All completed {} removed from dashboards {}".format(
            type, ", ".join(dashboards)), completed


class CleanupRequester:
    """
    Requests that cleanup of SIP files in the source directory be performed by
    another service.
    """

    def run(self):
        sip_ids = []
        for sip in SIP.objects.filter(process_status=SIP.APPROVED):
            r = requests.post(
                settings.CLEANUP_URL,
                data=json.dumps({"identifier": sip.bag_identifier}),
                headers={"Content-Type": "application/json"},
            )
            if r.status_code != 200:
                raise CleanupError(r.reason, sip.bag_identifier)
            sip.process_status = SIP.CLEANED_UP
            sip.save()
        message = "Requests sent to clean up SIPs." if len(
            sip_ids) else "No SIPS to clean up."
        return message, sip_ids


class CleanupRoutine:
    """Removes files in destination directory."""

    def __init__(self, identifier):
        self.identifier = identifier
        self.dest_dir = settings.DEST_DIR
        if not self.identifier:
            raise CleanupError(
                "No identifier submitted, unable to perform CleanupRoutine.",)

    def run(self):
        try:
            self.filepath = "{}.tar.gz".format(
                join(self.dest_dir, self.identifier))
            if isfile(self.filepath):
                remove(self.filepath)
                return "Transfer removed.", self.identifier
            return "Transfer was not found.", self.identifier
        except Exception as e:
            raise CleanupError(e, self.identifier)
