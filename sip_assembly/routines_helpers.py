import os

from asterism import file_helpers


def copy_to_directory(sip, dest):
    """Moves a bag to the `dest` directory and updates the object's bag_path."""
    dest_path = os.path.join(dest, "{}.tar.gz".format(sip.bag_identifier))
    copied = file_helpers.copy_file_or_dir(sip.bag_path, dest_path)
    if copied:
        sip.bag_path = dest_path
        sip.save()


def move_to_directory(sip, dest):
    """Moves a bag to the `dest` directory and updates the object's bag_path"""
    dest_path = os.path.join(dest, "{}.tar.gz".format(sip.bag_identifier))
    moved = file_helpers.move_file_or_dir(sip.bag_path, dest_path)
    if moved:
        sip.bag_path = os.path.join(dest_path)
        sip.save()


def extract_all(sip, extract_dir):
    """Extracts a tar.gz file to the `extract dir` directory"""
    ext = os.path.splitext(sip.bag_path)[-1]
    if ext in ['.tgz', '.tar.gz', '.gz']:
        extracted = file_helpers.tar_extract_all(sip.bag_path, extract_dir)
        if not extracted:
            raise Exception("Error extracting TAR file.")
        os.remove(sip.bag_path)
        sip.bag_path = os.path.join(extract_dir, sip.bag_identifier)
        sip.save()
    else:
        raise Exception("Unrecognized archive format")


def move_objects_dir(bag_path):
    """Moves the objects directory within a bag"""
    src = os.path.join(bag_path, 'data')
    dest = os.path.join(bag_path, 'data', 'objects')
    if not os.path.exists(dest):
        os.makedirs(dest)
    for fname in os.listdir(src):
        if fname != 'objects':
            os.rename(os.path.join(src, fname), os.path.join(dest, fname))


def create_structure(bag_path):
    """Creates Archivematica-compliant directory structure within a bag"""
    log_dir = os.path.join(bag_path, 'data', 'logs')
    md_dir = os.path.join(bag_path, 'data', 'metadata')
    docs_dir = os.path.join(
        bag_path,
        'data',
        'metadata',
        'submissionDocumentation')
    for dir in [log_dir, md_dir, docs_dir]:
        if not os.path.exists(dir):
            os.makedirs(dir)


# Right now this is a placeholder. There is currently no use case for adding
# submission documentation, but we might think of one in the future.
def create_submission_docs(sip):
    """Adds submission documentation to a bag. Currently a placeholder function"""
    return True


def add_processing_config(bag_path, data):
    """Adds pre-defined Archivematica processing configuration file"""
    with open(os.path.join(bag_path, 'processingMCP.xml'), 'w') as f:
        f.write(data)


def create_targz_package(sip):
    """Creates a compressed archive file from a bag"""
    tar_path = "{}.tar.gz".format(sip.bag_path)
    file_helpers.make_tarfile(
        sip.bag_path, tar_path, compressed=True, remove_src=True)
    sip.bag_path = tar_path
    sip.save()
