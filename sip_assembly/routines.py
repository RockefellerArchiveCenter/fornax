import json
from os import remove
from os.path import isdir, isfile, join

import requests
from amclient import AMClient, errors
from asterism import bagit_helpers, file_helpers
from fornax import settings
from sip_assembly import routines_helpers as helpers

from .csv_creator import CsvCreator
from .models import SIP


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
            raise Exception(errors.error_lookup(processing_config), processing_config)
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
                raise Exception("Directory does not exist", dir)

    def run(self):
        sip = SIP.objects.filter(process_status=SIP.CREATED).first()
        if sip:
            client = self.get_client(sip.origin)
            try:
                tmp_path = join(self.tmp_dir, "{}.tar.gz".format(sip.bag_identifier))
                file_helpers.copy_file_or_dir(sip.bag_path, tmp_path)
                extracted_path = helpers.extract_all(tmp_path, sip.bag_identifier, self.tmp_dir)
                bagit_helpers.validate(extracted_path)
                helpers.move_objects_dir(extracted_path)
                helpers.create_structure(extracted_path)
                if sip.data['rights_statements']:
                    CsvCreator(settings.ARCHIVEMATICA_VERSION).create_rights_csv(extracted_path, sip.data.get('rights_statements'))
                helpers.add_processing_config(
                    extracted_path, self.get_processing_config(client))
                bagit_helpers.update_bag_info(
                    extracted_path, {'Internal-Sender-Identifier': sip.bag_identifier})
                bagit_helpers.update_manifests(extracted_path)
                packaged_path = helpers.create_targz_package(extracted_path)
                destination_path = join(self.dest_dir, "{}.tar.gz".format(sip.bag_identifier))
                file_helpers.move_file_or_dir(packaged_path, destination_path)
                sip.process_status = SIP.ASSEMBLED
                sip.bag_path = destination_path
                sip.save()
                message = "All SIPs assembled.", [sip.bag_identifier]
            except Exception as e:
                file_helpers.remove_file_or_dir(join(self.tmp_dir, "{}.tar.gz".format(sip.bag_identifier)))
                file_helpers.remove_file_or_dir(join(self.tmp_dir, sip.bag_identifier))
                raise Exception("Error assembling SIP: {}".format(e), sip.bag_identifier)
        else:
            message = "No SIPS to assemble.", None
        return message


class SIPActions(ArchivematicaRoutine):
    """Performs various actions against the Archivematica API."""

    def create_package(self):
        """Starts and approves a transfer in Archivematica."""

        msg = "No transfers to start.", None
        if len(SIP.objects.filter(process_status=SIP.ASSEMBLED)):
            next_queued = SIP.objects.filter(
                process_status=SIP.ASSEMBLED).order_by('last_modified')[0]
            last_started = next(
                iter(SIP.objects.filter(process_status__in=[SIP.APPROVED, SIP.CLEANED_UP], origin=next_queued.origin).order_by('-last_modified')), None)
            client = self.get_client(next_queued.origin)
            try:
                if getattr(last_started, "archivematica_uuid", None) and client.get_unit_status(
                        last_started.archivematica_uuid) == 'PROCESSING':
                    msg = "Another transfer is processing, waiting until it finishes.", None
                else:
                    client.transfer_directory = "{}.tar.gz".format(
                        next_queued.bag_identifier)
                    client.transfer_name = next_queued.bag_identifier
                    client.transfer_type = 'zipped bag'
                    started = client.create_package()
                    next_queued.process_status = SIP.APPROVED
                    next_queued.archivematica_uuid = started.get("id")
                    next_queued.save()
                    msg = "Transfer started", [started.get("id")]
            except Exception as e:
                raise Exception(str(e), next_queued.bag_identifier)
        return msg

    def remove_completed(self, type):
        """Removes completed transfers and ingests from Archivematica dashboard."""
        all_completed = []
        dashboards = []
        for origin in settings.ARCHIVEMATICA:
            if settings.ARCHIVEMATICA[origin].get("close_completed"):
                client = self.get_client(origin)
                completed = getattr(client, 'close_completed_{}'.format((type)))()
                dashboards.append(origin)
                if completed.get('close_failed'):
                    raise Exception(
                        "Error removing {} from Archivematica dashboard".format(
                            type), completed['close_failed'])
                else:
                    all_completed += completed.get('close_succeeded', [])
        return "All completed {} removed from dashboards {}".format(
            type, ", ".join(dashboards)), all_completed


class CleanupRequester:
    """Requests cleanup of SIP files in the source directory by another service."""

    def run(self):
        sip_ids = []
        for sip in SIP.objects.filter(process_status=SIP.APPROVED):
            r = requests.post(
                settings.CLEANUP_URL,
                data=json.dumps({"identifier": sip.bag_identifier}),
                headers={"Content-Type": "application/json"})
            if r.status_code != 200:
                raise Exception(r.reason, sip.bag_identifier)
            sip.process_status = SIP.CLEANED_UP
            sip_ids.append(sip.bag_identifier)
            sip.save()
        message = "Requests sent to clean up SIPs." if len(
            sip_ids) else "No SIPS to clean up."
        return message, sip_ids


class CleanupRoutine:
    """Removes files in destination directory."""

    def __init__(self, identifier):
        self.identifier = identifier
        if not self.identifier:
            raise Exception(
                "No identifier submitted, unable to perform CleanupRoutine.", None)

    def run(self):
        try:
            self.filepath = "{}.tar.gz".format(
                join(settings.DEST_DIR, self.identifier))
            if isfile(self.filepath):
                remove(self.filepath)
                return "Transfer removed.", self.identifier
            return "Transfer was not found.", self.identifier
        except Exception as e:
            raise Exception(e, self.identifier)
