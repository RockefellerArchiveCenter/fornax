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
    def __init__(self, dirs):
        if dirs:
            self.upload_dir = dirs['upload']
            self.processing_dir = dirs['processing']
            self.delivery = dirs['delivery']
        else:
            self.upload_dir = settings.UPLOAD_DIR
            self.processing_dir = settings.PROCESSING_DIR
            self.delivery = settings.DELIVERY

    def run(self, sip):
        self.log = logger.new(object=sip)
        self.log.bind(request_id=str(uuid4()))
        if int(sip.process_status) < 20:
            try:
                library.move_to_directory(sip, self.processing_dir)
                library.extract_all(sip, self.processing_dir)
                library.validate(sip)
                sip.process_status = 20
                sip.save()
                self.log.debug("SIP moved to processing directory", request_id=str(uuid4()))
            except Exception as e:
                raise SIPAssemblyError("Error moving SIP to processing directory: {}".format(e))

        if int(sip.process_status) < 30:
            try:
                library.move_objects_dir(sip)
                library.create_structure(sip)
                sip.process_status = 30
                sip.save()
                self.log.debug("SIP restructured")
            except Exception as e:
                raise SIPAssemblyError("Error restructuring SIP: {}".format(e))

        if int(sip.process_status) < 40:
            if sip.data['rights_statements']:
                try:
                    library.create_rights_csv(sip)
                    library.validate_rights_csv(sip)
                except Exception as e:
                    raise SIPAssemblyError("Error creating rights.csv: {}".format(e))
            sip.process_status = 40
            sip.save()
            self.log.debug("Rights statements added to SIP")

        if int(sip.process_status) < 50:
            try:
                library.create_submission_docs(sip)
                sip.process_status = 50
                sip.save()
                self.log.debug("Submission docs created")
            except Exception as e:
                raise SIPAssemblyError("Error creating submission docs: {}".format(e))

        if int(sip.process_status) < 60:
            try:
                library.update_bag_info(sip)
                sip.process_status = 60
                sip.save()
                self.log.debug("Bag-info.txt updated")
            except Exception as e:
                raise SIPAssemblyError("Error updating bag-info.txt: {}".format(e))

        if int(sip.process_status) < 70:
            try:
                library.add_processing_config(sip)
                sip.process_status = 70
                sip.save()
                self.log.debug("Archivematica processing config added")
            except Exception as e:
                raise SIPAssemblyError("Error adding processing config: {}".format(e))

        if int(sip.process_status) < 80:
            try:
                library.update_manifests(sip)
                sip.process_status = 80
                sip.save()
                self.log.debug("Manifests updated")
            except Exception as e:
                raise SIPAssemblyError("Error updating manifests: {}".format(e))

        if int(sip.process_status) < 90:
            try:
                library.create_package(sip)
                library.deliver_via_rsync(sip, self.delivery['user'], self.delivery['host'])
                library.start_transfer(sip)
                sip.process_status = 90
                sip.save()
                self.log.debug("SIP sent to Archivematica")
            except Exception as e:
                raise SIPAssemblyError("Error sending SIP to Archivematica: {}".format(e))

        return True
