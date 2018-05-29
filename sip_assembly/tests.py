import json
from os.path import join, isdir
from os import listdir, environ, getenv
import random
import shutil
import vcr

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from fornax import settings
from sip_assembly.cron import AssembleSIPs, RetrieveFailed
from sip_assembly.models import SIP
from sip_assembly.views import SIPViewSet

to_process = 4
data_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'json')
bag_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'bags')
sip_assembly_vcr = vcr.VCR(
    serializer='json',
    cassette_library_dir='fixtures/cassettes',
    record_mode='once',
    match_on=['path', 'method'],
    filter_query_parameters=['username', 'password'],
    filter_headers=['Authorization', 'X-ArchivesSpace-Session'],
)


class ComponentTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user('aurora', 'aurora@example.com', 'aurorapass')
        if isdir(settings.TEST_UPLOAD_DIR):
            shutil.rmtree(settings.TEST_UPLOAD_DIR)
        shutil.copytree(bag_fixture_dir, settings.TEST_UPLOAD_DIR)

    def create_sip(self):
        print('*** Creating new SIPs ***')
        sip_count = 0
        for f in listdir(data_fixture_dir):
            with open(join(data_fixture_dir, f), 'r') as json_file:
                aurora_data = json.load(json_file)
                request = self.factory.post(reverse('sip-list'), aurora_data, format='json')
                force_authenticate(request, user=self.user)
                response = SIPViewSet.as_view(actions={"post": "create"})(request)
                sip_count += len(aurora_data['transfers'])
                self.assertEqual(response.status_code, 200, "Wrong HTTP code")
                print('Created SIPs')
        self.assertEqual(len(SIP.objects.all()), sip_count, "Incorrect number of SIPs created")
        return SIP.objects.all()

    def process_sip(self):
        print('*** Processing SIPs ***')
        with sip_assembly_vcr.use_cassette('process_sip.json'):
            AssembleSIPs().do(test=True)
        self.assertEqual(to_process, len([name for name in listdir(settings.TEST_TRANSFER_SOURCE_DIR) if isdir(join(settings.TEST_TRANSFER_SOURCE_DIR, name))]))

    def retrieve_failed(self):
        print('*** Retrieving failed accessions ***')
        with sip_assembly_vcr.use_cassette('retrieve_failed.json'):
            RetrieveFailed().do()

    def tearDown(self):
        for d in [settings.TEST_UPLOAD_DIR, settings.TEST_TRANSFER_SOURCE_DIR, settings.TEST_PROCESSING_DIR]:
            if isdir(d):
                shutil.rmtree(d)

    def test_sips(self):
        sips = self.create_sip()
        for sip in sips:
            sip.bag_path = join(settings.TEST_UPLOAD_DIR, sip.bag_identifier)
            sip.save()
        self.process_sip()
        self.retrieve_failed()
