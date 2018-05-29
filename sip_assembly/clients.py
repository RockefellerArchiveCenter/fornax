from electronbonder.client import ElectronBond
import json
import logging
from os.path import join
import requests
from structlog import wrap_logger
from uuid import uuid4

from fornax import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger = wrap_logger(logger)


class AuroraClientAuthError(Exception): pass


class AuroraClientDataError(Exception): pass


class AuroraClient(object):

    def __init__(self):
        self.log = logger.bind(transaction_id=str(uuid4()))
        self.client = ElectronBond(
            baseurl=settings.AURORA['baseurl'],
            username=settings.AURORA['username'],
            password=settings.AURORA['password'],
        )
        try:
            self.client.authorize()
        except Exception as e:
            self.log.error("Couldn't authenticate user credentials for Aurora")
            raise AuroraClientAuthError("Couldn't authenticate user credentials for Aurora")

    def retrieve(self, url, *args, **kwargs):
        self.log = self.log.bind(request_id=str(uuid4()))
        resp = self.client.get(url, *args, **kwargs)
        if resp.status_code != 200:
            self.log.error("Error retrieving data from Aurora: {msg}".format(msg=resp.json()['detail']))
            raise AuroraClientDataError("Error retrieving data from Aurora: {msg}".format(msg=resp.json()['detail']))
        self.log.debug("Object retrieved from Aurora", object=url)
        return resp.json()

    def retrieve_paged(self, url, *args, **kwargs):
        self.log = self.log.bind(request_id=str(uuid4()))
        try:
            resp = self.client.get_paged(url, *args, **kwargs)
            self.log.debug("List retrieved from Aurora", object=url)
            return resp
        except Exception as e:
            self.log.error("Error retrieving list from Aurora: {}".format(e))
            raise AuroraClientDataError(e)

    def update(self, url, data, *args, **kwargs):
        self.log = self.log.bind(request_id=str(uuid4()))
        resp = self.client.put(url, data=json.dumps(data), headers={"Content-Type":"application/json"}, *args, **kwargs)
        if resp.status_code != 200:
            self.log.error("Error saving data in Aurora: {msg}".format(msg=resp.json()['detail']))
            raise AuroraClientDataError("Error saving data in Aurora: {msg}".format(msg=resp.json()['detail']))
        self.log.debug("Object saved in Aurora", object=url)
        return resp.json()
