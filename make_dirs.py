import os
from fornax import settings

for dir in [settings.SRC_DIR, settings.TMP_DIR, settings.DEST_DIR]:
    if not os.path.isdir(dir):
        os.makedirs(dir)
