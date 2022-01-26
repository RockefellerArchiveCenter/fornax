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


class ProcessingException(Exception):
    pass


class ArchivematicaClientMixin:
    """Mixin to handle communication with Archivematica."""

    def get_client(self, origin):
        """Instantiates an Archivematica client based on SIP origin"""
        am_settings = settings.ARCHIVEMATICA_ORIGINS[origin]
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

    def remove_completed(self, type):
        """Removes completed transfers and ingests from Archivematica dashboard."""
        all_completed = []
        dashboards = []
        for origin in settings.ARCHIVEMATICA_ORIGINS:
            if settings.ARCHIVEMATICA_ORIGINS[origin].get("close_completed"):
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


class BaseRoutine(object):
    """Base routine which contains main run method."""

    def run(self):
        if not SIP.objects.filter(process_status=self.in_process_status).exists():
            sip = SIP.objects.filter(process_status=self.start_status).first()
            if sip:
                sip.process_status = self.in_process_status
                sip.save()
                try:
                    message = self.process_sip(sip)
                    sip.process_status = self.end_status
                    sip.save()
                except ProcessingException as e:
                    sip.process_status = self.start_status
                    sip.save()
                    message = str(e)
                except Exception as e:
                    sip.process_status = self.start_status
                    sip.save()
                    raise Exception(str(e), sip.bag_identifier)
            else:
                message = self.idle_message
        else:
            message = "Service currently running"
            sip = None
        return (message, [sip.bag_identifier] if sip else None)

    def process_sip(self, sip):
        raise NotImplementedError("You must implement a process_sip method")


class ExtractPackageRoutine(BaseRoutine):
    """Extracts compressed SIPs."""
    start_status = SIP.CREATED
    in_process_status = SIP.EXTRACTING
    end_status = SIP.EXTRACTED
    idle_message = "No SIPs to extract."

    def __init__(self):
        self.src_dir = settings.SRC_DIR
        self.tmp_dir = settings.TMP_DIR
        self.dest_dir = settings.DEST_DIR
        for dir in [self.src_dir, self.tmp_dir, self.dest_dir]:
            if not isdir(dir):
                raise Exception("Directory does not exist", dir)

    def process_sip(self, sip):
        tmp_path = join(self.tmp_dir, "{}.tar.gz".format(sip.bag_identifier))
        file_helpers.copy_file_or_dir(sip.bag_path, tmp_path)
        extracted_path = helpers.extract_all(tmp_path, sip.bag_identifier, self.tmp_dir)
        sip.bag_path = extracted_path
        return "SIP extracted."


class RestructurePackageRoutine(BaseRoutine, ArchivematicaClientMixin):
    """Restructures SIPs."""
    start_status = SIP.EXTRACTED
    in_process_status = SIP.RESTRUCTURING
    end_status = SIP.RESTRUCTURED
    idle_message = "No SIPs to restructure."

    def process_sip(self, sip):
        client = self.get_client(sip.origin)
        bagit_helpers.validate(sip.bag_path)
        helpers.move_objects_dir(sip.bag_path)
        helpers.create_structure(sip.bag_path)
        if sip.data['rights_statements']:
            CsvCreator(settings.ARCHIVEMATICA_VERSION, client).create_rights_csv(sip.bag_path, sip.data.get('rights_statements'))
        helpers.add_processing_config(
            sip.bag_path, self.get_processing_config(client))
        bagit_helpers.update_bag_info(
            sip.bag_path, {'Internal-Sender-Identifier': sip.bag_identifier})
        bagit_helpers.update_manifests(sip.bag_path)
        return "SIP restructured."


class AssemblePackageRoutine(BaseRoutine):
    """Packages SIPs."""
    start_status = SIP.RESTRUCTURED
    in_process_status = SIP.ASSEMBLING
    end_status = SIP.ASSEMBLED
    idle_message = "No SIPs to assemble."

    def process_sip(self, sip):
        packaged_path = helpers.create_targz_package(sip.bag_path)
        destination_path = join(settings.DEST_DIR, "{}.tar.gz".format(sip.bag_identifier))
        file_helpers.move_file_or_dir(packaged_path, destination_path)
        sip.bag_path = destination_path
        return "SIP assembled."


class StartPackageRoutine(BaseRoutine, ArchivematicaClientMixin):
    """Starts Archivematica transfer."""
    start_status = SIP.ASSEMBLED
    in_process_status = SIP.APPROVING
    end_status = SIP.APPROVED
    idle_message = "No transfers to start."

    def process_sip(self, sip):
        """Starts and approves a transfer in Archivematica."""
        last_started = SIP.objects.filter(process_status__in=[SIP.APPROVED, SIP.CLEANED_UP], origin=sip.origin).last()
        client = self.get_client(sip.origin)
        if getattr(last_started, "archivematica_uuid", None) and client.get_unit_status(last_started.archivematica_uuid)['status'] == 'PROCESSING':
            raise ProcessingException("Another transfer is processing, waiting until it finishes.")
        else:
            client.transfer_directory = "{}.tar.gz".format(
                sip.bag_identifier)
            client.transfer_name = sip.bag_identifier
            client.transfer_type = 'zipped bag'
            started = client.create_package()
            sip.archivematica_uuid = started.get("id")
            return "Transfer started."


class RemoveCompletedIngestsRoutine(ArchivematicaClientMixin):
    """Removes completed ingests from the Archivematica dashboard."""

    def run(self):
        return self.remove_completed("ingests")


class RemoveCompletedTransfersRoutine(ArchivematicaClientMixin):
    """Removes completed transfers from the Archivematica dashboard."""

    def run(self):
        return self.remove_completed("transfers")


class CleanupPackageRequester(BaseRoutine):
    """Requests cleanup of SIP files in the source directory by another service."""
    start_status = SIP.APPROVED
    in_process_status = SIP.CLEANING_UP
    end_status = SIP.CLEANED_UP
    idle_message = "No SIPs to clean up."

    def process_sip(self, sip):
        r = requests.post(
            settings.CLEANUP_URL,
            data=json.dumps({"identifier": sip.bag_identifier}),
            headers={"Content-Type": "application/json"})
        if r.status_code != 200:
            raise Exception(r.reason)
        return "Request sent to clean up SIP."


class CleanupPackageRoutine(object):
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
