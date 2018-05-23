from os import getenv
from os.path import join
import logging
from structlog import wrap_logger
from uuid import uuid4

from fornax import settings
from sip_assembly.models import SIP
from sip_assembly.clients import AuroraClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger = wrap_logger(logger)


class SIPAssembler(object):
    def __init__(self, test=None, aurora_client=None):
        if test:
            self.processing_dir = settings.TEST_PROCESSING_DIR
            self.transfer_source = settings.TEST_TRANSFER_SOURCE_DIR
        else:
            self.processing_dir = settings.PROCESSING_DIR
            self.transfer_source = settings.TRANSFER_SOURCE_DIR
        self.aurora_client = aurora_client if aurora_client else AuroraClient()

    def run(self, sip):
        self.log = logger.new(object=sip)
        try:
            if int(sip.process_status) < 20:
                data = self.aurora_client.retrieve(sip.aurora_uri)
                sip.data = data
                sip.save()

                if sip.archivesspace_identifier():
                    print("Moving SIP to processing directory")
                    self.log.bind(request_id=str(uuid4()))
                    if not sip.move_to_directory(join(settings.BASE_DIR, self.processing_dir, sip.bag_identifier)):
                        return False
                    sip.process_status = 20
                    sip.save()
                    self.log.debug("SIP moved to processing directory", request_id=str(uuid4()))

            if int(sip.process_status) < 30:
                print("Restructuring SIP")
                self.log.bind(request_id=str(uuid4()))
                if not sip.move_objects():
                    return False
                if not sip.create_structure():
                    self.log.error("Error creating new directories")
                    return False
                sip.process_status = 30
                sip.save()
                self.log.debug("SIP restructured")

            if int(sip.process_status) < 40:
                print("Creating rights statements")
                self.log.bind(request_id=str(uuid4()))
                if sip.data['rights_statements']:
                    if not sip.create_rights_csv():
                        self.log.error("Error creating rights statements")
                        return False
                    if not sip.validate_rights_csv():
                        self.log.error("rights.csv is invalid")
                        return False
                sip.process_status = 40
                sip.save()
                self.log.debug("Rights statements added to SIP")

            if int(sip.process_status) < 50:
                print("Creating submission docs")
                self.log.bind(request_id=str(uuid4()))
                if not sip.create_submission_docs():
                    self.log.error("Error creating submission docs")
                    return False
                sip.process_status = 50
                sip.save()
                self.log.debug("Submission docs created")

            if int(sip.process_status) < 60:
                print("Updating bag-info.txt")
                self.log.bind(request_id=str(uuid4()))
                if not sip.update_bag_info():
                    self.log.error("Error updating bag-info.txt")
                    return False
                sip.process_status = 60
                sip.save()
                self.log.debug("Bag-info.txt updated")

            if int(sip.process_status) < 70:
                print("Updating manifests")
                self.log.bind(request_id=str(uuid4()))
                if not sip.update_manifests():
                    self.log.error("Error updating manifests")
                    return False
                sip.process_status = 70
                sip.save()
                self.log.debug("Manifests updated")

            if int(sip.process_status) < 90:
                print("Sending SIP to Archivematica")
                self.log.bind(request_id=str(uuid4()))
                if not sip.move_to_directory(join(settings.BASE_DIR, self.transfer_source, sip.bag_identifier)):
                    self.log.error("Error sending SIP to Archivematica")
                    return False
                sip.process_status = 90
                sip.save()
                self.log.debug("SIP sent to Archivematica")

            return True

        except Exception as e:
            print(e)
