import json
from os.path import join, isdir
from os import listdir, makedirs
import shutil
import vcr

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from fornax import settings
from sip_assembly.routines import SIPAssembler, CleanupRoutine, CleanupRequester
from sip_assembly.models import SIP
from sip_assembly.views import (
    SIPViewSet,
    CreatePackageView,
    RemoveCompletedIngestsView,
    RemoveCompletedTransfersView,
    SIPAssemblyView,
    CleanupRoutineView,
    CleanupRequestView)

data_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'json')
bag_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'bags')

assembly_vcr = vcr.VCR(
    serializer='json',
    cassette_library_dir='fixtures/cassettes',
    record_mode='once',
    match_on=['path', 'method'],
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
                request = self.factory.post(
                    reverse('sip-list'), aurora_data, format='json')
                response = SIPViewSet.as_view(
                    actions={"post": "create"})(request)
                self.assertEqual(response.status_code, 200, "Wrong HTTP code")
                print('Created SIPs')
        self.assertEqual(len(SIP.objects.all()),
                         len(listdir(data_fixture_dir)),
                         "Incorrect number of SIPs created")
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
            CleanupRoutine(
                sip.bag_identifier, dirs={
                    "dest": self.dest_dir}).run()
        self.assertEqual(0, len(listdir(self.dest_dir)))

    def archivematica_views(self):
        with assembly_vcr.use_cassette('archivematica.json'):
            print('*** Starting transfer ***')
            request = self.factory.post(reverse('create-transfer'))
            response = CreatePackageView.as_view()(request)
<<<<<<< HEAD
            self.assertEqual(
                response.status_code,
                200,
                "Response error: {}".format(
                    response.data))
            self.assertEqual(
                response.data['count'],
                1,
                "Only one transfer should be started")
=======
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], 1, "Only one transfer should be started")
>>>>>>> master
        with assembly_vcr.use_cassette('archivematica_cleanup.json'):
            print('*** Cleaning up transfers ***')
            request = self.factory.post(reverse('remove-transfers'))
            response = RemoveCompletedTransfersView.as_view()(request)
<<<<<<< HEAD
            self.assertEqual(
                response.status_code,
                200,
                "Response error: {}".format(
                    response.data))
            self.assertEqual(
                response.data['count'],
                0,
                "Wrong number of objects processed")
            print('*** Cleaning up ingests ***')
            request = self.factory.post(reverse('remove-ingests'))
            response = RemoveCompletedIngestsView.as_view()(request)
            self.assertEqual(
                response.status_code,
                200,
                "Response error: {}".format(
                    response.data))
            self.assertEqual(
                response.data['count'],
                0,
                "Wrong number of objects processed")
=======
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], 0, "Wrong number of objects processed")
            print('*** Cleaning up ingests ***')
            request = self.factory.post(reverse('remove-ingests'))
            response = RemoveCompletedIngestsView.as_view()(request)
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], 0, "Wrong number of objects processed")
>>>>>>> master

    def request_cleanup(self):
        print('*** Requesting cleanup ***')
        with assembly_vcr.use_cassette('request_cleanup.json'):
            cleanup = CleanupRequester(
                'http://ursa-major-web:8005/cleanup/').run()
            self.assertNotEqual(False, cleanup)

    def run_view(self):
        with assembly_vcr.use_cassette('process_sip.json'):
            print('*** Test run view ***')
            request = self.factory.post(
                reverse('assemble-sip'), {"test": True})
            response = SIPAssemblyView.as_view()(request)
<<<<<<< HEAD
            self.assertEqual(
                response.status_code,
                200,
                "Response error: {}".format(
                    response.data))
            self.assertEqual(
                response.data['count'], len(
                    SIP.objects.filter(
                        process_status=SIP.CREATED)), "Wrong number of objects processed")
=======
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], len(SIP.objects.filter(process_status=SIP.CREATED)), "Wrong number of objects processed")
>>>>>>> master

    def cleanup_view(self):
        print('*** Test cleanup view ***')
        for sip in SIP.objects.all():
            request = self.factory.post(
                reverse('cleanup'), data={
                    "test": True, "identifier": sip.bag_identifier})
            response = CleanupRoutineView.as_view()(request)
<<<<<<< HEAD
            self.assertEqual(
                response.status_code,
                200,
                "Response error: {}".format(
                    response.data))
            self.assertEqual(
                response.data['count'],
                1,
                "Wrong number of objects processed")
=======
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], 1, "Wrong number of objects processed")
>>>>>>> master

    def request_cleanup_view(self):
        print('*** Test request cleanup view ***')
        with assembly_vcr.use_cassette('request_cleanup.json'):
            request = self.factory.post(reverse('request-cleanup'))
            response = CleanupRequestView.as_view()(request)
<<<<<<< HEAD
            self.assertEqual(
                response.status_code,
                200,
                "Response error: {}".format(
                    response.data))
            self.assertEqual(
                response.data['count'], len(
                    SIP.objects.filter(
                        process_status=SIP.APPROVED)), "Wrong number of objects processed")
=======
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], len(SIP.objects.filter(process_status=SIP.APPROVED)), "Wrong number of objects processed")
>>>>>>> master

    def schema(self):
        print('*** Getting schema view ***')
        schema = self.client.get(reverse('schema'))
<<<<<<< HEAD
        self.assertEqual(
            schema.status_code,
            200,
            "Response error: {}".format(schema))
=======
        self.assertEqual(schema.status_code, 200, "Response error: {}".format(schema))
>>>>>>> master

    def health_check(self):
        print('*** Getting status view ***')
        status = self.client.get(reverse('api_health_ping'))
<<<<<<< HEAD
        self.assertEqual(
            status.status_code,
            200,
            "Response error: {}".format(status))
=======
        self.assertEqual(status.status_code, 200, "Response error: {}".format(status))
>>>>>>> master

    def tearDown(self):
        for d in [self.src_dir, self.tmp_dir, self.dest_dir]:
            if isdir(d):
                shutil.rmtree(d)

    def test_sips(self):
        sips = self.create_sip()
        for sip in sips:
            sip.bag_path = join(
                self.src_dir, "{}.tar.gz".format(
                    sip.bag_identifier))
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
