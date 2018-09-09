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

from django.contrib.postgres.fields import JSONField
from django.db import models

logger = wrap_logger(logger=logging.getLogger(__name__))


class SIPError(Exception): pass


class RightsError(Exception): pass


class SIP(models.Model):
    PROCESS_STATUS_CHOICES = (
        (10, "New SIP created"),
        (20, "SIP files moved to processing"),
        (30, "SIP validated according to BagIt"),
        (30, "SIP restructured"),
        (40, "PREMIS CSV rights added to SIP"),
        (50, "Submission documentation added to SIP"),
        (60, "SIP bag-info.txt updated"),
        (70, "SIP Manifests updated"),
        (90, "SIP Delivered to Archivematica Transfer Source"),
    )
    process_status = models.CharField(max_length=100, choices=PROCESS_STATUS_CHOICES)
    bag_path = models.CharField(max_length=100)
    bag_identifier = models.CharField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now_add=True)
    data = JSONField(null=True, blank=True)

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

    def move_objects_dir(self):
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
            logger.error("Error moving objects directory: {}".format(e), object=self)
            raise SIPError("Error moving objects directory: {}".format(e))

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
        filepath = join(self.bag_path, 'data', 'metadata', 'rights.csv')
        mode = 'w'
        for rights_statement in self.data.get('rights_statements'):
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
                    for file in listdir(join(self.bag_path, 'data', 'objects')):
                        for rights_granted in rights_statement.get('rights_granted'):
                            csvwriter.writerow(
                                [file, rights_statement.get('rights_basis', ''), rights_statement.get('status', ''),
                                 rights_statement.get('determination_date', ''), rights_statement.get('jurisdiction', ''),
                                 rights_statement.get('start_date', ''), rights_statement.get('end_date', ''),
                                 rights_statement.get('terms', ''), rights_statement.get('citation', ''),
                                 rights_statement.get('note', ''), rights_granted.get('act', ''),
                                 rights_granted.get('restriction', ''), rights_granted.get('start_date', ''),
                                 rights_granted.get('end_date', ''), rights_granted.get('note', ''),
                                 rights_statement.get('doc_id_type', ''), rights_statement.get('doc_id_value', ''),
                                 rights_statement.get('doc_id_role', '')])
                    logger.debug("Row for Rights Statement created in rights.csv", object=rights_statement)
                logger.debug("rights.csv saved", object=filepath)
            except Exception as e:
                logger.error("Error saving rights.csv: {}".format(e), object=self)
                raise RightsError("Error saving rights.csv: {}".format(e))
        return True

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
        validator.add_value_check('status', enumeration('copyrighted', 'public domain', 'unknown', ''),
                                  'EX4', 'invalid status')
        validator.add_value_check('grant_act', enumeration('publish', 'disseminate', 'replicate', 'migrate', 'modify', 'use', 'delete'),
                                  'EX5', 'invalid act')
        validator.add_value_check('grant_restriction', enumeration('allow', 'disallow', 'conditional'),
                                  'EX6', 'invalid restriction')
        for field in ['file', 'note', 'grant_note']:
            validator.add_value_check(field, str,
                                      'EX7', 'field must exist')

        def check_dates(r):
            for field in [r['determination_date'], r['start_date'], r['end_date'], r['grant_start_date'], r['grant_end_date']]:
                format = True
                try:
                    datetime.datetime.strptime(field, '%Y-%m-%d')
                except ValueError:
                    format = False
                valid = (format or field == 'OPEN')
            if not valid:
                raise RecordError('EX8', 'invalid date format')
        validator.add_record_check(check_dates)

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
            bag.info['Internal-Sender-Identifier'] = self.data['identifier']
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
