import bagit
import base64
import csv
from csvvalidator import *
import datetime
import logging
from os import listdir, makedirs, rename, remove, walk
from os.path import basename, dirname, exists, isfile, isdir, join, splitext
import psutil
import requests
import shutil
from structlog import wrap_logger
import subprocess
import tarfile

from fornax import settings

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
        (70, "Archivematica processing config added"),
        (80, "SIP Manifests updated"),
        (90, "SIP Delivered to Archivematica Transfer Source"),
    )
    process_status = models.CharField(max_length=100, choices=PROCESS_STATUS_CHOICES)
    bag_path = models.CharField(max_length=100)
    bag_identifier = models.CharField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now=True)
    last_modified = models.DateTimeField(auto_now_add=True)
    data = JSONField(null=True, blank=True)

    def move_to_directory(self, dest):
        """Moves a bag to the `dest` directory"""
        try:
            if not exists(dest):
                makedirs(dest)
            shutil.move(self.bag_path, join(dest, "{}.tar.gz".format(self.bag_identifier)))
            self.bag_path = join(dest, "{}.tar.gz".format(self.bag_identifier))
            self.save()
            return True
        except Exception as e:
            logger.error("Error moving SIP to directory {}: {}".format(dest, e), object=self)
            raise SIPError("Error moving SIP to directory {}: {}".format(dest, e))

    def extract_all(self, extract_dir):
        """Extracts a tar.gz file to the `extract dir` directory"""
        ext = splitext(self.bag_path)[-1]
        if ext in ['.tgz', '.tar.gz', '.gz']:
            tf = tarfile.open(self.bag_path, 'r')
            tf.extractall(extract_dir)
            tf.close()
            remove(self.bag_path)
            self.bag_path = join(extract_dir, self.bag_identifier)
            self.save()
            return True
        else:
            logger.error("Unrecognized archive format: {}".format(ext), object=self)
            raise SIPError("Unrecognized archive format: {}".format(ext))

    def validate(self):
        """Validates a bag against the BagIt specification"""
        bag = bagit.Bag(self.bag_path)
        return bag.validate()

    def move_objects_dir(self):
        """Moves the objects directory within a bag"""
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
        """Creates Archivematica-compliant directory structure within a bag"""
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
        """Creates Archivematica-compliant CSV containing PREMIS rights"""
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
                                ["data/objects/{}".format(file), rights_statement.get('rights_basis', ''), rights_statement.get('status', ''),
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
                return False
        return True

    def validate_rights_csv(self):
        """Validate a CSV to ensure it complies with Archivematica validation"""
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
        """Adds submission documentation to a bag. Currently a placeholder function"""
        return True

    def update_bag_info(self):
        """Adds metadata to `bag-info.txt`"""
        try:
            bag = bagit.Bag(self.bag_path)
            bag.info['Internal-Sender-Identifier'] = self.data['identifier']
            bag.save()
            return True
        except Exception as e:
            logger.error("Error updating bag-info metadata: {}".format(e), object=self)
            raise SIPError("Error updating bag-info metadata: {}".format(e))

    def add_processing_config(self):
        """Adds pre-defined Archivematica processing configuration file"""
        try:
            config = join(settings.PROCESSING_CONFIG_DIR, settings.PROCESSING_CONFIG)
            shutil.copyfile(config, join(self.bag_path, 'processingMCP.xml'))
            return True
        except Exception as e:
            logger.error("Error creating processing config: {}".format(e), object=self)
            raise SIPError("Error creating processing config: {}".format(e))

    def update_manifests(self):
        """Updates bag manifests according to BagIt specification"""
        try:
            bag = bagit.Bag(self.bag_path)
            bag.save(manifests=True)
            return True
        except Exception as e:
            logger.error("Error updating bag manifests: {}".format(e), object=self)
            raise SIPError("Error updating bag manifests: {}".format(e))

    def create_package(self):
        """Creates a compressed archive file from a bag"""
        try:
            with tarfile.open('{}.tar.gz'.format(self.bag_path), "w:gz") as tar:
                tar.add(self.bag_path, arcname=basename(self.bag_path))
                tar.close()
            shutil.rmtree(self.bag_path)
            self.bag_path = '{}.tar.gz'.format(self.bag_path)
            self.save()
            return True
        except Exception as e:
            logger.error("Error creating .tar.gz archive: {}".format(e), object=self)
            raise SIPError("Error creating .tar.gz archive: {}".format(e))

    def deliver_via_rsync(self, user, host):
        rsynccmd = "rsync -avh --remove-source-files {} {}".format(self.bag_path, host)
        rsyncproc = subprocess.Popen(rsynccmd, shell=True,
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,)
        # while True:
        #     next_line = rsyncproc.stdout.readline().decode("utf-8")
        #     if not next_line:
        #         break
        #     print(next_line)

        ecode = rsyncproc.wait()
        if ecode != 0:
            logger.error("Error delivering bag to {}".format(host), object=self)
            raise SIPError("Error delivering bag to {}".format(host))
        return True

    def start_transfer(self):
        headers = {"Authorization": "ApiKey {}:{}".format(settings.ARCHIVEMATICA['username'], settings.ARCHIVEMATICA['api_key'])}
        baseurl = settings.ARCHIVEMATICA['baseurl']
        path = "/home/{}.tar.gz".format(self.bag_identifier)
        full_url = join(baseurl, 'transfer/start_transfer/')
        paths = "{}:{}".format(settings.ARCHIVEMATICA['location_uuid'], path)
        params = {'name': self.bag_identifier, 'type': 'zipped bag', 'paths[]': base64.b64encode(paths.encode())}
        start = requests.post(full_url, headers=headers, data=params)
        if start:
            return True
            # This block sends a POST request to start transfers. However it may be better to use the Archivematica automation tools for this
            # approve = requests.post(join(baseurl, 'transfer/approve_transfer/'), headers=headers, data={'type': 'zipped bag', 'directory': '{}.tar.gz'.format(self.bag_identifier)})
            # if approve:
            #     return True
        else:
            raise SIPError("Error starting transfer in Archivematica: {}".format(start['data']['message']))
