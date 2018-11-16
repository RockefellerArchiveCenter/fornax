import logging
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
    def __init__(self, dirs=None):
        if dirs:
            self.upload_dir = dirs['upload']
            self.processing_dir = dirs['processing']
            self.delivery = dirs['delivery']
        else:
            self.upload_dir = settings.UPLOAD_DIR
            self.processing_dir = settings.PROCESSING_DIR
            self.delivery = settings.DELIVERY

    def run(self):
        self.log = logger.new(request_id=str(uuid4()))
        self.log.debug("Found {} SIPs to process".format(len(SIP.objects.filter(process_status=10))))
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
                library.deliver_via_rsync(sip, self.delivery['user'], self.delivery['host'])
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

    def start_transfer(self):
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
