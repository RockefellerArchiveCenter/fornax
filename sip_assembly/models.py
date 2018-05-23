import bagit
import csv
from csvvalidator import *
import datetime
import logging
from os import listdir, makedirs, rename, walk
from os.path import join, isfile, isdir, exists, dirname
import psutil
import shutil
from structlog import wrap_logger

from django.db import models

logger = wrap_logger(logger=logging.getLogger(__name__))


class SIPError(Exception): pass


class RightsError(Exception): pass


class SIP(models.Model):
    aurora_uri = models.URLField()
    component_uri = models.URLField(null=True, blank=True)
    PROCESS_STATUS_CHOICES = (
        (10, "New transfer created"),
        (20, "SIP files moved to processing"),
        (30, "SIP validated according to BagIt"),
        (30, "SIP restructured"),
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

    def open_files(self):
        path_list = []
        for proc in psutil.process_iter():
            open_files = proc.open_files()
            if open_files:
                for fileObj in open_files:
                    path_list.append(fileObj.path)
        return path_list

    def dir_list(self, dir):
        file_list = []
        for path, subdirs, files in walk(dir):
            for name in files:
                file_list.append(join(path, name))
        return file_list

    def has_open_files(self):
        if not isdir(self.bag_path):
            return True
        if set(self.open_files()).intersection(set(self.dir_list(self.bag_path))):
            print(set(self.open_files()).intersection(set(self.dir_list(self.bag_path))))
            return True
        return False

    def move_to_directory(self, dest):
        try:
            self.validate()
            shutil.move(self.bag_path, dest)
            self.bag_path = dest
            self.save()
            self.validate()
            return True
        except Exception as e:
            logger.error("Error moving SIP to directory {}: {}".format(dest, e), object=self)
            raise SIPError("Error moving SIP to directory {}: {}".format(dest, e))

    def validate(self):
        bag = bagit.Bag(self.bag_path)
        return bag.validate()

    def move_objects(self):
        src = join(self.bag_path, 'data')
        dest = join(self.bag_path, 'data', 'objects')
        try:
            if not exists(dest):
                makedirs(dest)
            for fname in listdir(src):
                if fname != 'objects':
                    rename(join(src, fname), join(dest, fname))
            return True
        except Exception as e:
            logger.error("Error moving objects: {}".format(e), object=self)
            raise SIPError("Error moving objects: {}".format(e))

    def create_structure(self):
        log_dir = join(self.bag_path, 'data', 'logs')
        md_dir = join(self.bag_path, 'data', 'metadata')
        docs_dir = join(self.bag_path, 'data', 'metadata', 'submissionDocumentation')
        try:
            for dir in [log_dir, md_dir, docs_dir]:
                if not exists(dir):
                    makedirs(dir)
            return True
        except Exception as e:
            logger.error("Error creating new SIP structure: {}".format(e), object=self)
            raise SIPError("Error creating new SIP structure: {}".format(e))

    def create_rights_csv(self):
        for rights_statement in RightsStatement.objects.filter(sip=self):
            return rights_statement.save_csv(self.bag_path)

    def validate_rights_csv(self):
        field_names = (
               'file', 'basis', 'status', 'determination_date', 'jurisdiction',
               'start_date', 'end_date', 'terms', 'citation', 'note', 'grant_act',
               'grant_restriction', 'grant_start_date', 'grant_end_date',
               'grant_note', 'doc_id_type', 'doc_id_value', 'doc_id_role'
               )

        validator = CSVValidator(field_names)

        validator.add_header_check('EX1', 'bad header')
        validator.add_record_length_check('EX2', 'unexpected record length')
        validator.add_value_check('basis', enumeration('Copyright', 'Statute', 'License', 'Other'),
                                  'EX3', 'invalid basis')
        validator.add_value_check('status', enumeration('copyrighted', 'public domain', 'unknown'),
                                  'EX4', 'invalid status')
        validator.add_value_check('grant_act', enumeration('publish', 'disseminate', 'replicate', 'migrate', 'modify', 'use', 'delete'),
                                  'EX5', 'invalid act')
        validator.add_value_check('grant_restriction', enumeration('allow', 'disallow', 'conditional'),
                                  'EX6', 'invalid restriction')
        for field in ['file', 'note', 'grant_note']:
            validator.add_value_check(field, str,
                                      'EX7', 'field must exist')
        for field in ['determination_date', 'start_date', 'end_date', 'grant_start_date', 'grant_end_date']:
            validator.add_value_check(field, datetime_string('%Y-%m-%d'),
                                      'EX8', 'invalid date format')

        with open(join(self.bag_path, 'data', 'metadata', 'rights.csv'), 'r') as csvfile:
            data = csv.reader(csvfile)
            problems = validator.validate(data)
            if problems:
                for problem in problems:
                    logger.error(problem)
                raise RightsError(problems)
            else:
                return True

    # Right now this is a placeholder. There is currently no use case for adding
    # submission documentation, but we might think of one in the future.
    def create_submission_docs(self):
        return True

    def update_bag_info(self):
        try:
            bag = bagit.Bag(self.bag_path)
            bag.info['Internal-Sender-Identifier'] = self.component_uri
            bag.save()
            return True
        except Exception as e:
            logger.error("Error updating bag-info metadata: {}".format(e), object=self)
            raise SIPError("Error updating bag-info metadata: {}".format(e))

    def update_manifests(self):
        try:
            bag = bagit.Bag(self.bag_path)
            bag.save(manifests=True)
            return True
        except Exception as e:
            logger.error("Error updating bag manifests: {}".format(e), object=self)
            raise SIPError("Error updating bag manifests: {}".format(e))


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

    def initial_save(self, rights_statements, sip, log):
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
                    log.debug("Rights statement saved", object=rights_statement)

    def save_csv(self, target):
        filepath = join(target, 'data', 'metadata', 'rights.csv')
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
                    logger.debug("Row for Rights Statement created in rights.csv", object=self)
            logger.debug("rights.csv saved", object=filepath)
            return True
        except Exception as e:
            logger.error("Error saving rights.csv: {}".format(e), object=self)
            raise RightsError("Error saving rights.csv: {}".format(e))
