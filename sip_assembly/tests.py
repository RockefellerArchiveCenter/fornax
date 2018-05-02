import json
from os.path import join, isdir
from os import listdir, environ, getenv
import random
import shutil
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth.models import User
from fornax import settings
from sip_assembly.cron import AssembleSIPs
from sip_assembly.models import SIP, RightsStatement
from sip_assembly.views import SIPViewSet

data_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'json')
bag_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'bags')


class ComponentTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user('aurora', 'aurora@example.com', 'aurorapass')
        if isdir(settings.TEST_UPLOAD_DIR):
            shutil.rmtree(settings.TEST_UPLOAD_DIR)
        shutil.copytree(bag_fixture_dir, settings.TEST_UPLOAD_DIR)

    def create_sip(self):
        print('*** Creating new SIPs ***')
        for f in listdir(data_fixture_dir):
            with open(join(data_fixture_dir, f), 'r') as json_file:
                aurora_data = json.load(json_file)
                request = self.factory.post(reverse('sip-list'), aurora_data, format='json')
                force_authenticate(request, user=self.user)
                response = SIPViewSet.as_view(actions={"post": "create"})(request)
                self.assertEqual(response.status_code, 200, "Wrong HTTP code")
                print('Created SIP {name}'.format(name=response.data['url']))
        self.assertEqual(len(SIP.objects.all()), len(listdir(data_fixture_dir)), "Incorrect number of SIPs created")
        return SIP.objects.all()

    def process_sip(self):
        print('*** Processing SIPs ***')
        self.assertIsNot(False, AssembleSIPs().do())

    def tearDown(self):
        if isdir(settings.TEST_UPLOAD_DIR):
            shutil.rmtree(settings.TEST_UPLOAD_DIR)
        if isdir(settings.TRANSFER_SOURCE_DIR):
            shutil.rmtree(settings.TRANSFER_SOURCE_DIR)

    def test_sips(self):
        sips = self.create_sip()
        for sip in sips:
            sip.bag_path = join(settings.TEST_UPLOAD_DIR, sip.bag_identifier)
            sip.save()
        self.process_sip()
