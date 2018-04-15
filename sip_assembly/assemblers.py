from sip_assembly.models import SIP


class SIPAssembler(object):

    def run(self, sip):
        if not sip.validate():
            return False

        if not sip.create_rights_csv(data['rights_statements']): # URIs for rights statements
            return False

        if not sip.create_submission_docs():
            return False

        if not sip.update_bag_info(): # what exactly needs to be updated here?
            return False

        if not sip.send_to_archivematica():
            return False

        if not sip.rebag():
            return False

        if not sip.validate():
            return False

        return True
