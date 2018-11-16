import os
from fornax import settings

for dir in [settings.UPLOAD_DIR, settings.PROCESSING_DIR]:
    if not os.path.isdir(dir):
        os.makedirs(dir)
