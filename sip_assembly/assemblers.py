from sip_assembly.models import SIP
from os.path import join

from fornax import settings


class SIPAssembler(object):

    def run(self, sip):
        try:
            # move to processing dir
            sip.process_status = 20
            sip.save()

            print("Validating SIP")
            if not sip.validate():
                return False
            sip.process_status = 30
            sip.save()

            print("Restructuring SIP")
            if not sip.move_objects():
                print("Error moving existing objects")
                return False
            if not sip.create_structure():
                print("Error creating new directories")
                return False
            sip.process_status = 35
            sip.save()
            print("SIP restructured")

            print("Creating rights statements")
            if not sip.create_rights_csv():
                print("Error creating rights statements")
                return False
            sip.process_status = 40
            sip.save()
            print("Rights statements added to SIP")

            print("Creating submission docs")
            if not sip.create_submission_docs():
                print("Error creating submission docs")
                return False
            sip.process_status = 50
            sip.save()
            print("Submission docs created")

            print("Updating bag-info.txt")
            if not sip.update_bag_info():
                print("Error updating bag-info.txt")
                return False
            sip.process_status = 60
            sip.save()
            print("Bag-info.txt updated")

            print("Updating manifests")
            if not sip.update_manifests():
                print("Error updating manifests")
                return False
            sip.process_status = 70
            sip.save()
            print("Manifests updated")

            print("Validating SIP")
            if not sip.validate():
                print("Error validating SIP")
                return False
            sip.process_status = 80
            sip.save()
            print("SIP validated")

            print("Sending SIP to Archivematica")
            if not sip.send_to_archivematica():
                print("Error sending SIP to Archivematica")
                return False
            sip.process_status = 90
            sip.save()
            print("SIP sent to Archivematica")

            return True

        except Exception as e:
            print(e)
