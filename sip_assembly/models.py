import bagit
import datetime
from django.db import models
from sip_assembly.clients import AuroraClient


class SIP(models.Model):
    aurora_uri = models.URLField()
    component_uri = models.URLField(null=True, blank=True)
    PROCESS_STATUS_CHOICES = (
        (10, "New transfer created"),
        (20, "SIP files moved to processing"),
        (30, "SIP validated according to BagIt"),
        (40, "PREMIS CSV rights added"),
        (50, "Submission documentation added"),
        (60, "bag-info.txt updated"),
        (70, "Manifests updated"),
        (80, "SIP validated"),
        (90, "Delivered to Archivematica Transfer Source")
    )
    process_status = models.CharField(max_length=100, choices=PROCESS_STATUS_CHOICES)
    machine_file_path = models.CharField(max_length=100) #review (bag_path)
    machine_file_upload_time = models.DateTimeField() #review (bag_upload?)
    machine_file_identifier = models.CharField(max_length=255, unique=True) #review - do we need this?? (bag_identifier)
    created_time = models.DateTimeField(auto_now=True)
    modified_time = models.DateTimeField(auto_now_add=True)

    def validate(self):
        bag = bagit.Bag(self.machine_file_path)
        return bag.validate()

    def create_rights_csv(self):
        for rights_statement in RightsStatement.objects.filter(sip=self):
            if not rights_statement.save_csv(self.machine_file_path):
                return False
        return True

    def create_submission_docs(self):
        return True

    # what exactly needs to be updated here? Component URI?
    def update_bag_info(self):
        try:
            bag = bagit.Bag(self.machine_file_path)
            # bag.info['key'] = "blah"
            bag.save()
            return True
        except Exception as e:
            print(e)
            return False

    def update_manifests(self):
        try:
            bag = bagit.Bag(self.machine_file_path)
            bag.save(manifests=True)
            return True
        except Exception as e:
            print(e)
            return False

    def send_to_archivematica(self):
        return True


class RightsStatement(models.Model):
    sip = models.ForeignKey(SIP, on_delete="CASCADE")
    BASIS_CHOICES = (
        ('Copyright', 'Copyright'),
        ('Statute', 'Statute'),
        ('License', 'License'),
        ('Other', 'Other')
    )
    basis = models.CharField(choices=BASIS_CHOICES, max_length=64)
    STATUS_CHOICES = (
        ('copyrighted', 'copyrighted'),
        ('public domain', 'public domain'),
        ('unknown', 'unknown'),
    )
    status = models.CharField(choices=STATUS_CHOICES, max_length=64, null=True, blank=True)
    determination_date = models.DateField(blank=True, null=True)
    jurisdiction = models.CharField(max_length=2, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    terms = models.TextField(blank=True, null=True)
    citation = models.TextField(blank=True, null=True)
    note = models.TextField()
    GRANT_ACT_CHOICES = (
        ('publish', 'Publish'),
        ('disseminate', 'Disseminate'),
        ('replicate', 'Replicate'),
        ('migrate', 'Migrate'),
        ('modify', 'Modify'),
        ('use', 'Use'),
        ('delete', 'Delete'),
    )
    grant_act = models.CharField(choices=GRANT_ACT_CHOICES, max_length=64)
    GRANT_RESTRICTION_CHOICES = (
        ('allow', 'Allow'),
        ('disallow', 'Disallow'),
        ('conditional', 'Conditional'),
    )
    grant_restriction = models.CharField(choices=GRANT_RESTRICTION_CHOICES, max_length=64)
    grant_start_date = models.DateField(blank=True, null=True)
    grant_end_date = models.DateField(blank=True, null=True)
    rights_granted_note = models.TextField()
    doc_id_role = models.CharField(max_length=255, blank=True, null=True)
    doc_id_type = models.CharField(max_length=255, blank=True, null=True)
    doc_id_value = models.CharField(max_length=255, blank=True, null=True)

    def initial_save(self, uri, sip):
        client = AuroraClient()
        rights_data = client.get(uri)
        if getattr(rights_data, 'basis') == 'Other':
            basis_key = 'other_rights'
        else:
            basis_key = getattr(rights_data, 'basis').lower()
        if 'rights_granted' in rights_data:
            for grant in rights_data['rights_granted']:
                rights_statement = RightsStatement(
                    sip=sip,
                    basis=getattr(rights_data, 'basis'),
                    status=getattr(rights_data, 'copyright_status', None),
                    determination_date=getattr(rights_data, '{}_determination_date'.format(basis_key), None),
                    jurisdiction=getattr(rights_data, '{}_jurisdiction'.format(basis_key), None),
                    start_date=getattr(rights_data, '{}_start_date'.format(basis_key), None),
                    end_date=getattr(rights_data, '{}_end_date'.format(basis_key), None),
                    terms=getattr(rights_data, 'license_terms', None),
                    citation=getattr(rights_data, 'statute_citation', None),
                    note=getattr(rights_data, '{}_note'.format(basis_key), None),
                    grant_act=getattr(grant, 'act', None),
                    grant_restriction=getattr(grant, 'restriction', None),
                    grant_start_date=getattr(grant, 'start_date', None),
                    grant_end_date=getattr(grant, 'end_date', None),
                    rights_granted_note=getattr(grant, 'rights_granted_note', None),
                )
                rights_statement.save()

    def save_csv(self, filepath):
        # save the rightsstatement as CSV at the designated filepath
        return True
