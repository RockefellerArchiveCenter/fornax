import json
from os.path import join, isdir
from os import listdir, makedirs, remove
import random
import shutil
import vcr

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from fornax import settings
from sip_assembly.assemblers import SIPAssembler, CleanupRoutine, CleanupRequester
from sip_assembly.models import SIP
from sip_assembly.views import SIPViewSet, SIPAssemblyView, StartTransferView, ApproveTransferView, CleanupRoutineView, CleanupRequestView

data_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'json')
bag_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'bags')

assembly_vcr = vcr.VCR(
    serializer='json',
    cassette_library_dir='fixtures/cassettes',
    record_mode='once',
    match_on=['path', 'method', 'query'],
    filter_query_parameters=['username', 'password'],
    filter_headers=['Authorization'],
)


class SIPAssemblyTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.src_dir = settings.TEST_SRC_DIR
        self.tmp_dir = settings.TEST_TMP_DIR
        self.dest_dir = settings.TEST_DEST_DIR
        if isdir(self.src_dir):
            shutil.rmtree(self.src_dir)
        shutil.copytree(bag_fixture_dir, self.src_dir)
        for dir in [self.tmp_dir, self.dest_dir]:
            if not isdir(dir):
                makedirs(dir)

    def create_sip(self):
        print('*** Creating new SIPs ***')
        for f in listdir(data_fixture_dir):
            with open(join(data_fixture_dir, f), 'r') as json_file:
                aurora_data = json.load(json_file)
                request = self.factory.post(reverse('sip-list'), aurora_data, format='json')
                response = SIPViewSet.as_view(actions={"post": "create"})(request)
                self.assertEqual(response.status_code, 200, "Wrong HTTP code")
                print('Created SIPs')
        self.assertEqual(len(SIP.objects.all()), len(listdir(data_fixture_dir)), "Incorrect number of SIPs created")
        return SIP.objects.all()

    def process_sip(self):
        with assembly_vcr.use_cassette('process_sip.json'):
            print('*** Processing SIPs ***')
            assembly = SIPAssembler(dirs={'src': self.src_dir,
                                          'tmp': self.tmp_dir,
                                          'dest': self.dest_dir}).run()
            self.assertNotEqual(False, assembly)

    def cleanup_sip(self):
        print('*** Cleaning up ***')
        for sip in SIP.objects.all():
            cleanup = CleanupRoutine(sip.bag_identifier, dirs={"dest": self.dest_dir}).run()
        self.assertEqual(0, len(listdir(self.dest_dir)))

    def archivematica_views(self):
        with assembly_vcr.use_cassette('archivematica.json'):
            print('*** Starting transfer ***')
            request = self.factory.post(reverse('start-transfer'))
            response = StartTransferView.as_view()(request)
            self.assertEqual(response.status_code, 200, "Wrong HTTP code")
            print('*** Approving transfer ***')
            request = self.factory.post(reverse('start-transfer'))
            response = ApproveTransferView.as_view()(request)
            self.assertEqual(response.status_code, 200, "Wrong HTTP code")

    def request_cleanup(self):
        print('*** Requesting cleanup ***')
        with assembly_vcr.use_cassette('request_cleanup.json'):
            cleanup = CleanupRequester('http://ursa-major-web:8005/cleanup/').run()
            self.assertNotEqual(False, cleanup)

    def run_view(self):
        print('*** Test run view ***')
        request = self.factory.post(reverse('assemble-sip'), {"test": True})
        response = SIPAssemblyView.as_view()(request)
        self.assertEqual(response.status_code, 200, "Wrong HTTP code")

    def cleanup_view(self):
        print('*** Test cleanup view ***')
        for sip in SIP.objects.all():
            request = self.factory.post(reverse('cleanup'), data={"identifier": sip.bag_identifier})
            response = CleanupRoutineView.as_view()(request)
            self.assertEqual(response.status_code, 200, "Wrong HTTP code")

    def request_cleanup_view(self):
        print('*** Test cleanup view ***')
        with assembly_vcr.use_cassette('request_cleanup.json'):
            request = self.factory.post(reverse('request-cleanup'))
            response = CleanupRequestView.as_view()(request)
            self.assertEqual(response.status_code, 200, "Wrong HTTP code")

    def schema(self):
        print('*** Getting schema view ***')
        schema = self.client.get(reverse('schema-json', kwargs={"format": ".json"}))
        self.assertEqual(schema.status_code, 200, "Wrong HTTP code")

    def health_check(self):
        print('*** Getting status view ***')
        status = self.client.get(reverse('api_health_ping'))
        self.assertEqual(status.status_code, 200, "Wrong HTTP code")

    def tearDown(self):
        for d in [self.src_dir, self.tmp_dir, self.dest_dir]:
            if isdir(d):
                shutil.rmtree(d)

    def test_sips(self):
        sips = self.create_sip()
        for sip in sips:
            sip.bag_path = join(self.src_dir, "{}.tar.gz".format(sip.bag_identifier))
            sip.save()
        self.process_sip()
        self.cleanup_sip()
        self.archivematica_views()
        self.request_cleanup()
        self.run_view()
        self.cleanup_view()
        self.request_cleanup_view()
        self.schema()
        self.health_check()
