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
            raise ArchivematicaClientException("Could not return a valid response for {}".format(full_url))

    def send_start_transfer_request(self, sip):
        """Starts a transfer in Archivematica."""
        basepath = "/home/{}.tar.gz".format(sip.bag_identifier)
        full_url = join(self.baseurl, 'transfer/start_transfer/')
        bagpaths = "{}:{}".format(self.location_uuid, basepath)
        params = {'name': sip.bag_identifier, 'type': 'zipped bag',
                  'paths[]': base64.b64encode(bagpaths.encode())}
        start = requests.post(full_url, headers=self.headers, data=params)
        if start.status_code != 200:
            message = start.json()['message'] if start.json()['message'] else start.reason
            raise ArchivematicaClientException(message)

    def send_approve_transfer_request(self, sip):
        """Approves a transfer in Archivematica."""
        approve_transfer = requests.post(join(self.baseurl, 'transfer/approve_transfer/'),
                                         headers=self.headers,
                                         data={'type': 'zipped bag', 'directory': '{}.tar.gz'.format(sip.bag_identifier)})
        if approve_transfer.status_code != 200:
            raise ArchivematicaClientException(approve_transfer.json()['message'])

    def send_ingest_cleanup_request(self):
        """Removes completed ingests."""
        completed = self.retrieve('ingest/completed').json()
        for uuid in completed['results']:
            full_url = join(self.baseurl, 'ingest/{}/delete/'.format(uuid))
            resp = requests.delete(full_url, headers=self.headers).json()
            if not resp['removed']:
                raise ArchivematicaClientException("Error removing ingest {}".format(uuid))
        return len(completed['results'])

    def send_transfer_cleanup_request(self):
        """Removes completed transfers."""
        completed = self.retrieve('transfer/completed').json()
        for uuid in completed['results']:
            full_url = join(self.baseurl, 'transfer/{}/delete/'.format(uuid))
            resp = requests.delete(full_url, headers=self.headers).json()
            if not resp['removed']:
                raise ArchivematicaClientException("Error removing transfer {}".format(uuid))
        return len(completed['results'])
