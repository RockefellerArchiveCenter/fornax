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
        if response.status_code == 200:
            if response.headers['content-type'] == 'application/json':
                return response.json()
            else:
                return response
        else:
            raise ArchivematicaClientException("Could not return a valid response for {}".format(full_url))

    def start_transfer(self, sip):
        """Starts a transfer in Archivematica."""
        basepath = "{}.tar.gz".format(sip.bag_identifier)
        full_url = join(self.baseurl, 'transfer/start_transfer/')
        bagpaths = "{}:{}".format(self.location_uuid, basepath)
        params = {'name': sip.bag_identifier, 'type': 'zipped bag',
                  'paths[]': base64.b64encode(bagpaths.encode())}
        start = requests.post(full_url, headers=self.headers, data=params)
        if start.status_code != 200:
            message = start.json()['message'] if start.json()['message'] else start.reason
            raise ArchivematicaClientException(message)

    def approve_transfer(self, sip):
        """Approves a transfer in Archivematica."""
        approve_transfer = requests.post(join(self.baseurl, 'transfer/approve_transfer/'),
                                         headers=self.headers,
                                         data={'type': 'zipped bag', 'directory': '{}.tar.gz'.format(sip.bag_identifier)})
        if approve_transfer.status_code != 200:
            raise ArchivematicaClientException(approve_transfer.json()['message'])

    def cleanup(self, type):
        """Removes completed ingests and transfers."""
        if type not in ["ingest", "transfer"]:
            raise ArchivematicaClientException("Unknown type {}".format(type))
        completed = self.retrieve('{}/completed'.format(type))
        for uuid in completed['results']:
            full_url = join(self.baseurl, '{}/{}/delete/'.format(type, uuid))
            resp = requests.delete(full_url, headers=self.headers).json()
            if not resp['removed']:
                raise ArchivematicaClientException(uuid)
        return completed['results']
