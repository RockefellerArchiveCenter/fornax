import logging
from structlog import wrap_logger
from uuid import uuid4

from fornax import settings
from sip_assembly import library
from sip_assembly.models import SIP

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
        for sip in SIP.objects.filter(process_status=10):
            self.log = logger.bind(object=sip)
            try:
                library.move_to_directory(sip, self.processing_dir)
                library.extract_all(sip, self.processing_dir)
                library.validate(sip)
                library.move_objects_dir(sip)
                library.create_structure(sip)
                if sip.data['rights_statements']:
                    try:
                        library.create_rights_csv(sip)
                        library.validate_rights_csv(sip)
                    except Exception as e:
                        raise SIPAssemblyError("Error creating rights.csv: {}".format(e))
                library.update_bag_info(sip)
                library.add_processing_config(sip)
                library.update_manifests(sip)
                library.create_package(sip)
                library.deliver_via_rsync(sip, self.delivery['user'], self.delivery['host'])
                sip.process_status = 20
                sip.save()
            except Exception as e:
                raise SIPAssemblyError("Error assembling SIP: {}".format(e))

        return True


class SIPActions(object):
    def __init__(self):
        self.headers = {"Authorization": "ApiKey {}:{}".format(settings.ARCHIVEMATICA['username'],
                        settings.ARCHIVEMATICA['api_key']), 'Accept': 'application/json',
                        'User-Agent': 'Fornax/0.1'}
        self.baseurl = settings.ARCHIVEMATICA['baseurl']

    def start_transfer(self):
        if len(SIP.objects.filter(process_status=20)):
            try:
                sip = SIP.objects.filter(process_status=20)[0]
                library.send_start_transfer_request(sip, self.baseurl, self.headers)
                sip.process_status = 30
                sip.save()
                return sip.bag_identifier
            except Exception as e:
                raise SIPAssemblyError("Error starting transfer in Archivematica: {}".format(e))
        else:
            return "No transfers to start."

    def approve_transfer(self):
        if len(SIP.objects.filter(process_status=30)):
            try:
                sip = SIP.objects.filter(process_status=30)[0]
                library.send_approve_transfer_request(sip, self.baseurl, self.headers)
                sip.process_status = 40
                sip.save()
                return sip.bag_identifier
            except Exception as e:
                raise SIPAssemblyError("Error approving transfer in Archivematica: {}".format(e))
        else:
            return "No transfers to approve."
