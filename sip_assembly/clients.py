from os.path import join
import json
import logging
import requests
from structlog import wrap_logger
from fornax import settings
from uuid import uuid4

logger = wrap_logger(logging.getLogger(__name__))


class AuroraClient(object):

    def __init__(self):
        log = logger.new(transaction_id=str(uuid4()))
        # NOT IMPLEMENTED IN AURORA YET
        # username=settings.AURORA['username'],
        # password=settings.AURORA['password'],
        # if not client.authorize()
        #   log.error("Couldn't authenticate to Aurora")
        pass

    def get(self, uri):
        resp = requests.get(uri)
        if resp.status_code != 200:
            return False
        return resp.json()
