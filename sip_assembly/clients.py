import base64
import json
from os.path import join
import requests


class ArchivematicaClientException(Exception): pass


class ArchivematicaClient(object):
    def __init__(self, username, api_key, baseurl, location_uuid):
        self.headers = {"Authorization": "ApiKey {}:{}".format(username, api_key)}
        self.baseurl = baseurl
        self.location_uuid = location_uuid

    def retrieve(self, uri, *args, **kwargs):
        full_url = "/".join([self.baseurl.rstrip("/"), uri.lstrip("/")])
        response = requests.get(full_url, headers=self.headers, *args, **kwargs)
        if response:
            return response
        else:
            raise ArchivematicaClientError("Could not return a valid response for {}".format(full_url))

    def send_start_transfer_request(self, sip):
        """Starts and approves transfer in Archivematica."""
        basepath = "/home/{}.tar.gz".format(sip.bag_identifier)
        full_url = join(self.baseurl, 'transfer/start_transfer/')
        bagpaths = "{}:{}".format(self.location_uuid, basepath)
        params = {'name': sip.bag_identifier, 'type': 'zipped bag',
                  'paths[]': base64.b64encode(bagpaths.encode())}
        start = requests.post(full_url, headers=self.headers, data=params)
        if start.status_code != 200:
            raise ArchivematicaClientException(start.json()['message'])

    def send_approve_transfer_request(self, sip):
        approve_transfer = requests.post(join(self.baseurl, 'transfer/approve_transfer/'),
                                         headers=self.headers,
                                         data={'type': 'zipped bag', 'directory': '{}.tar.gz'.format(sip.bag_identifier)})
        if approve_transfer.status_code != 200:
            raise ArchivematicaClientException(approve_transfer.json()['message'])
