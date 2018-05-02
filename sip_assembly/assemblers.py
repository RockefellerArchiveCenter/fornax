from os.path import join
import logging
from structlog import wrap_logger
from uuid import uuid4

from fornax import settings
from sip_assembly.models import SIP

logger = wrap_logger(logger=logging.getLogger(__name__))


class SIPAssembler(object):

    def run(self, sip):
        self.log = logger.new(object=sip)
        try:
            print("Moving SIP to processing directory")
            self.log.bind(request_id=str(uuid4()))
            if not sip.move_to_directory(settings.PROCESSING_DIR):
                self.log.error("SIP invalid")
                return False
            sip.process_status = 20
            sip.save()
            self.log.debug("SIP moved to processing directory", request_id=str(uuid4()))

            print("Validating SIP")
            self.log.bind(request_id=str(uuid4()))
            if not sip.validate():
                self.log.error("SIP invalid")
                return False
            sip.process_status = 30
            sip.save()
            self.log.debug("SIP validated")

            print("Restructuring SIP")
            self.log.bind(request_id=str(uuid4()))
            if not sip.move_objects():
                self.log.error("Error moving existing objects")
                return False
            if not sip.create_structure():
                self.log.error("Error creating new directories")
                return False
            sip.process_status = 35
            sip.save()
            self.log.debug("SIP restructured")

            print("Creating rights statements")
            self.log.bind(request_id=str(uuid4()))
            if not sip.create_rights_csv():
                self.log.error("Error creating rights statements")
                return False
            sip.process_status = 40
            sip.save()
            self.log.debug("Rights statements added to SIP")

            print("Creating submission docs")
            self.log.bind(request_id=str(uuid4()))
            if not sip.create_submission_docs():
                self.log.error("Error creating submission docs")
                return False
            sip.process_status = 50
            sip.save()
            self.log.debug("Submission docs created")

            print("Updating bag-info.txt")
            self.log.bind(request_id=str(uuid4()))
            if not sip.update_bag_info():
                self.log.error("Error updating bag-info.txt")
                return False
            sip.process_status = 60
            sip.save()
            self.log.debug("Bag-info.txt updated")

            print("Updating manifests")
            self.log.bind(request_id=str(uuid4()))
            if not sip.update_manifests():
                self.log.error("Error updating manifests")
                return False
            sip.process_status = 70
            sip.save()
            self.log.debug("Manifests updated")

            print("Validating SIP")
            self.log.bind(request_id=str(uuid4()))
            if not sip.validate():
                self.log.error("Error validating SIP")
                return False
            sip.process_status = 80
            sip.save()
            self.log.debug("SIP validated")

            print("Sending SIP to Archivematica")
            self.log.bind(request_id=str(uuid4()))
            if not sip.move_to_directory():
                self.log.error("Error sending SIP to Archivematica")
                return False
            sip.process_status = 90
            sip.save()
            self.log.debug("SIP sent to Archivematica")

            return True

        except Exception as e:
            print(e)
