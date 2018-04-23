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

    def get_rights_statements(self, uri):
        # resp = requests.get(uri)
        # if resp.status_code != 200:
        #     return False
        # return resp.json()['rights_statements']
        return [{
            "note": "Closed for 137 days from end date",
            "determination_date": "2018-04-11",
            "end_date": "2126-06-16",
            "rights_granted": [
                {
                    "act": "disseminate",
                    "start_date": "1982-05-14",
                    "end_date": "1999-06-17",
                    "rights_granted_note": "Dissemination is restricted for 10 years after end date",
                    "restriction": "disallow"
                }
            ],
            "rights_basis": "Copyright",
            "jurisdiction": "us",
            "start_date": "1982-05-14"
        }]
