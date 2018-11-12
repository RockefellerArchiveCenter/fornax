import bagit
import csv
from csvvalidator import *
import datetime
import logging
import os
import shutil
from structlog import wrap_logger
import subprocess
import tarfile

from fornax import settings
from .clients import ArchivematicaClient

logger = wrap_logger(logger=logging.getLogger(__name__))


def move_to_directory(sip, dest):
    """Moves a bag to the `dest` directory"""
    try:
        if not os.path.exists(dest):
            os.makedirs(dest)
        shutil.move(sip.bag_path, os.path.join(dest, "{}.tar.gz".format(sip.bag_identifier)))
        sip.bag_path = os.path.join(dest, "{}.tar.gz".format(sip.bag_identifier))
        sip.save()
        return True
    except Exception as e:
        logger.error("Error moving SIP to directory {}: {}".format(dest, e), object=sip)
        return False


def extract_all(sip, extract_dir):
    """Extracts a tar.gz file to the `extract dir` directory"""
    ext = os.path.splitext(sip.bag_path)[-1]
    if ext in ['.tgz', '.tar.gz', '.gz']:
        tf = tarfile.open(sip.bag_path, 'r')
        tf.extractall(extract_dir)
        tf.close()
        os.remove(sip.bag_path)
        sip.bag_path = os.path.join(extract_dir, sip.bag_identifier)
        sip.save()
        return True
    else:
        logger.error("Unrecognized archive format: {}".format(ext), object=sip)
        return False


def move_objects_dir(sip):
    """Moves the objects directory within a bag"""
    src = os.path.join(sip.bag_path, 'data')
    dest = os.path.join(sip.bag_path, 'data', 'objects')
    try:
        if not os.path.exists(dest):
            os.makedirs(dest)
        for fname in os.listdir(src):
            if fname != 'objects':
                os.rename(os.path.join(src, fname), os.path.join(dest, fname))
        return True
    except Exception as e:
        logger.error("Error moving objects directory: {}".format(e), object=sip)
        return False


def validate(sip):
    """Validates a bag against the BagIt specification"""
    bag = bagit.Bag(sip.bag_path)
    return bag.validate()


def create_structure(sip):
    """Creates Archivematica-compliant directory structure within a bag"""
    log_dir = os.path.join(sip.bag_path, 'data', 'logs')
    md_dir = os.path.join(sip.bag_path, 'data', 'metadata')
    docs_dir = os.path.join(sip.bag_path, 'data', 'metadata', 'submissionDocumentation')
    try:
        for dir in [log_dir, md_dir, docs_dir]:
            if not os.path.exists(dir):
                os.makedirs(dir)
        return True
    except Exception as e:
        logger.error("Error creating new SIP structure: {}".format(e), object=sip)
        return False


def create_rights_csv(sip):
    """Creates Archivematica-compliant CSV containing PREMIS rights"""
    filepath = os.path.join(sip.bag_path, 'data', 'metadata', 'rights.csv')
    mode = 'w'
    for rights_statement in sip.data.get('rights_statements'):
        firstrow = ['file', 'basis', 'status', 'determination_date', 'jurisdiction',
                    'start_date', 'end_date', 'terms', 'citation', 'note', 'grant_act',
                    'grant_restriction', 'grant_start_date', 'grant_end_date',
                    'grant_note', 'doc_id_type', 'doc_id_value', 'doc_id_role']
        if os.path.isfile(filepath):
            mode = 'a'
            firstrow = None
        try:
            if not os.path.exists(os.path.dirname(filepath)):
                os.makedirs(os.path.dirname(filepath))
            with open(filepath, mode) as csvfile:
                csvwriter = csv.writer(csvfile)
                if firstrow:
                    csvwriter.writerow(firstrow)
                for file in os.listdir(os.path.join(sip.bag_path, 'data', 'objects')):
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
            logger.error("Error saving rights.csv: {}".format(e), object=sip)
            return False
    return True


def validate_rights_csv(sip):
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

    with open(os.path.join(sip.bag_path, 'data', 'metadata', 'rights.csv'), 'r') as csvfile:
        data = csv.reader(csvfile)
        problems = validator.validate(data)
        if problems:
            for problem in problems:
                logger.error(problem)
            return False
        else:
            return True


# Right now this is a placeholder. There is currently no use case for adding
# submission documentation, but we might think of one in the future.
def create_submission_docs(sip):
    """Adds submission documentation to a bag. Currently a placeholder function"""
    return True


def update_bag_info(sip):
    """Adds metadata to `bag-info.txt`"""
    try:
        bag = bagit.Bag(sip.bag_path)
        bag.info['Internal-Sender-Identifier'] = sip.data['identifier']
        bag.save()
        return True
    except Exception as e:
        logger.error("Error updating bag-info metadata: {}".format(e), object=sip)
        return False


def add_processing_config(sip):
    """Adds pre-defined Archivematica processing configuration file"""
    try:
        response = ArchivematicaClient().retrieve('processing-configuration/{}/'.format(settings.ARCHIVEMATICA['processing_config']))
        with open(os.path.join(sip.bag_path, 'processingMCP.xml'), 'wb') as f:
            f.write(response.content)
            return True
    except Exception as e:
        logger.error("Error creating processing config: {}".format(e), object=sip)
        return False


def update_manifests(sip):
    """Updates bag manifests according to BagIt specification"""
    try:
        bag = bagit.Bag(sip.bag_path)
        bag.save(manifests=True)
        return True
    except Exception as e:
        logger.error("Error updating bag manifests: {}".format(e), object=sip)
        return False


def create_package(sip):
    """Creates a compressed archive file from a bag"""
    try:
        with tarfile.open('{}.tar.gz'.format(sip.bag_path), "w:gz") as tar:
            tar.add(sip.bag_path, arcname=os.path.basename(sip.bag_path))
            tar.close()
        shutil.rmtree(sip.bag_path)
        sip.bag_path = '{}.tar.gz'.format(sip.bag_path)
        sip.save()
        return True
    except Exception as e:
        logger.error("Error creating .tar.gz archive: {}".format(e), object=sip)
        return False


def deliver_via_rsync(sip, user, host):
    rsynccmd = "rsync -avh --remove-source-files {} {}".format(sip.bag_path, host)
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
        logger.error("Error delivering bag to {}".format(host), object=sip)
        return False
    return True
