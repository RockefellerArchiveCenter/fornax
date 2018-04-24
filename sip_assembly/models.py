import bagit
import csv
import datetime
from os import listdir, makedirs
from os.path import join, isfile, exists, dirname
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
    bag_path = models.CharField(max_length=100)
    bag_identifier = models.CharField(max_length=255, unique=True)
    created_time = models.DateTimeField(auto_now=True)
    modified_time = models.DateTimeField(auto_now_add=True)

    def validate(self):
        bag = bagit.Bag(self.bag_path)
        return bag.validate()

    def create_rights_csv(self):
        for rights_statement in RightsStatement.objects.filter(sip=self):
            if not rights_statement.save_csv(self.bag_path):
                return False
        return True

    # TODO: Build this out
    def create_submission_docs(self):
        return True

    # TODO: what exactly needs to be updated here? Component URI?
    def update_bag_info(self):
        try:
            bag = bagit.Bag(self.bag_path)
            # bag.info['key'] = "blah"
            bag.save()
            return True
        except Exception as e:
            print(e)
            return False

    def update_manifests(self):
        try:
            bag = bagit.Bag(self.bag_path)
            bag.save(manifests=True)
            return True
        except Exception as e:
            print(e)
            return False

    def send_to_archivematica(self):
        return True


class RightsStatement(models.Model):
    sip = models.ForeignKey(SIP, on_delete="CASCADE", related_name='rights_statements')
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
    grant_note = models.TextField()
    doc_id_role = models.CharField(max_length=255, blank=True, null=True)
    doc_id_type = models.CharField(max_length=255, blank=True, null=True)
    doc_id_value = models.CharField(max_length=255, blank=True, null=True)

    def initial_save(self, rights_statements, sip):
        for rights_data in rights_statements:
            if 'rights_granted' in rights_data:
                for grant in rights_data['rights_granted']:
                    rights_statement = RightsStatement(
                        sip=sip,
                        basis=rights_data.get('rights_basis'),
                        status=rights_data.get('status', None),
                        determination_date=rights_data.get('determination_date', None),
                        jurisdiction=rights_data.get('jurisdiction', None),
                        start_date=rights_data.get('start_date', None),
                        end_date=rights_data.get('end_date', None),
                        terms=rights_data.get('license_terms', None),
                        citation=rights_data.get('citation', None),
                        note=rights_data.get('note', None),
                        grant_act=grant.get('act', None),
                        grant_restriction=grant.get('restriction', None),
                        grant_start_date=grant.get('start_date', None),
                        grant_end_date=grant.get('end_date', None),
                        grant_note=grant.get('rights_granted_note', None),
                    )
                    rights_statement.save()

    def save_csv(self, target):
        filepath = join(target, 'metadata', 'rights.csv')
        mode = 'w'
        firstrow = ['file', 'basis', 'status', 'determination_date', 'jurisdiction',
                    'start_date', 'end_date', 'terms', 'citation', 'note', 'grant_act',
                    'grant_restriction', 'grant_start_date', 'grant_end_date',
                    'grant_note', 'doc_id_type', 'doc_id_value', 'doc_id_role']
        if isfile(filepath):
            mode = 'a'
            firstrow = None
        try:
            if not exists(dirname(filepath)):
                makedirs(dirname(filepath))
            with open(filepath, mode) as csvfile:
                csvwriter = csv.writer(csvfile)
                if firstrow:
                    csvwriter.writerow(firstrow)
                for file in listdir(join(target, 'data')):
                    csvwriter.writerow(
                        [file, self.basis, self.status, self.determination_date,
                         self.jurisdiction, self.start_date, self.end_date,
                         self.terms, self.citation, self.note, self.grant_act,
                         self.grant_restriction, self.grant_start_date,
                         self.grant_end_date, self.grant_note,
                         self.doc_id_type, self.doc_id_value, self.doc_id_role])
            return True
        except Exception as e:
            print(e)
