import json
from os.path import join
import random
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth.models import User
from fornax import settings
from sip_assembly.cron import RunSIPAssembly
from sip_assembly.models import SIP, RightsStatement
from sip_assembly.views import SIPViewSet
from sip_assembly.clients import AuroraClient

sip_count = 5


class ComponentTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user('aurora', 'aurora@example.com', 'aurorapass')
        with open(join(settings.BASE_DIR, 'sample_data/aurora.json'), 'r') as json_file:
            self.aurora_data = json.load(json_file)

    def create_sip(self):
        print('*** Creating new SIPs ***')
        for n in range(sip_count):
            request = self.factory.post(reverse('sip-list'), self.aurora_data, format='json')
            force_authenticate(request, user=self.user)
            response = SIPViewSet.as_view(actions={"post": "create"})(request)
            self.assertEqual(response.status_code, 200, "Wrong HTTP code")
            print('Created SIP {name}'.format(name=response.data['url']))
        self.assertEqual(len(SIP.objects.all()), sip_count, "Incorrect number of SIPs created")
        return SIP.objects.all()

    def aurora_client(self):
        print('*** Testing Aurora client ***')
        self.assertTrue(AuroraClient().get(self.aurora_data['url']))

    def process_sip(self):
        print('*** Processing SIPs ***')
        self.assertTrue(RunSIPAssembly())

    def test_sips(self):
        self.create_sip()
        self.aurora_client()
        self.process_sip()
