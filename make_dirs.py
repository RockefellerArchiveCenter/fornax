import os
from fornax import settings

"""
This file is called by entrypoint.sh (when running this application in a
container) to ensure that the necessary directories exist.
"""

for dir in [settings.SRC_DIR, settings.TMP_DIR, settings.DEST_DIR]:
    if not os.path.isdir(dir):
        os.makedirs(dir)
