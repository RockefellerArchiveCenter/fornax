import os

from asterism import file_helpers


def extract_all(sip_path, sip_identifier, extract_dir):
    """Extracts a tar.gz file to the `extract dir` directory"""
    ext = os.path.splitext(sip_path)[-1]
    if ext in ['.tgz', '.tar.gz', '.gz']:
        extracted = file_helpers.tar_extract_all(sip_path, extract_dir)
        if not extracted:
            raise Exception("Error extracting TAR file.")
        os.remove(sip_path)
        return os.path.join(extract_dir, sip_identifier)
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


def create_targz_package(sip_path):
    """Creates a compressed archive file from a bag"""
    tar_path = "{}.tar.gz".format(sip_path)
    file_helpers.make_tarfile(
        sip_path, tar_path, compressed=True, remove_src=True)
    return tar_path


def recursive_chmod(dir, mode=0o775):
    """Sets file and directory permissions recursively."""
    for root, dirs, files in os.walk(dir):
        for d in dirs:
            os.chmod(os.path.join(root, d), mode)
        for f in files:
            os.chmod(os.path.join(root, f), mode)
