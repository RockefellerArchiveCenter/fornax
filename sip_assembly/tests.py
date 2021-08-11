import json
import shutil
from os import listdir, makedirs
from os.path import isdir, join

import vcr
from django.test import TestCase
from django.urls import reverse
from fornax import settings
from rest_framework.test import APIRequestFactory
from sip_assembly.models import SIP
from sip_assembly.routines import (CleanupRequester, CleanupRoutine,
                                   SIPAssembler)
from sip_assembly.views import (CleanupRequestView, CleanupRoutineView,
                                CreatePackageView, RemoveCompletedIngestsView,
                                RemoveCompletedTransfersView, SIPAssemblyView,
                                SIPViewSet)

from .csv_creator import CsvCreator

data_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'json')
bag_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'bags')
csv_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'csv_creation')

assembly_vcr = vcr.VCR(serializer='json', cassette_library_dir='fixtures/cassettes', record_mode='once', match_on=['path', 'method'], filter_query_parameters=['username', 'password'], filter_headers=['Authorization'],)


class CsvCreatorTest(TestCase):
    def setUp(self):
        self.tmp_dir = settings.TMP_DIR
        if isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
        makedirs(self.tmp_dir)
        for directory in ['aurora_example', 'digitization_example']:
            shutil.copytree(join(csv_fixture_dir, directory), join(self.tmp_dir, directory))

    def test_run(self):
        print(join(csv_fixture_dir, "{}.json".format("aurora_example")))
        with open(join(csv_fixture_dir, "{}.json".format("aurora_example")), 'r') as json_file:
            json_data = json.load(json_file)
        created_csv = CsvCreator().run(join(self.tmp_dir, "aurora_example"), json_data["bag_data"]["rights_statements"])
        self.assertEqual(created_csv, "CSV {} created.".format(join(self.tmp_dir, 'aurora_example', 'data', 'metadata', 'rights.csv')))

    def test_get_rights_rows(self):
        csv_creator = CsvCreator()
        csv_creator.bag_path = join(self.tmp_dir, 'digitization_example')
        with open(join(csv_fixture_dir, "{}.json".format("digitization_example")), 'r') as json_file:
            json_data = json.load(json_file)
        csv_creator.rights_statements = json_data["bag_data"]["rights_statements"]
        rights_rows = csv_creator.get_rights_rows(join(self.tmp_dir, 'digitization_example', 'data', 'objects'), "sample.txt")
        self.assertEqual(len(rights_rows), 2)
        for row in rights_rows:
            self.assertEqual(len(row), 18)

    def tearDown(self):
        if isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)


class SIPAssemblyTest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.src_dir = settings.SRC_DIR
        self.tmp_dir = settings.TMP_DIR
        self.dest_dir = settings.DEST_DIR
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
            self.assertEqual(response.status_code, 201, "Wrong HTTP code")
            print('Created SIPs')
        self.assertEqual(len(SIP.objects.all()), len(listdir(data_fixture_dir)), "Incorrect number of SIPs created")
        return SIP.objects.all()

    def process_sip(self):
        with assembly_vcr.use_cassette('process_sip.json'):
            print('*** Processing SIPs ***')
            assembly = SIPAssembler().run()
            self.assertNotEqual(False, assembly)

    def cleanup_sip(self):
        print('*** Cleaning up ***')
        for sip in SIP.objects.all():
            CleanupRoutine(
                sip.bag_identifier).run()
        self.assertEqual(0, len(listdir(self.dest_dir)))

    def archivematica_views(self):
        for cassette, view_str, view, count in [
                ('archivematica.json', 'create-transfer', CreatePackageView, 1),
                ('archivematica_cleanup.json', 'remove-transfers', RemoveCompletedTransfersView, 0),
                ('archivematica_cleanup.json', 'remove-ingests', RemoveCompletedIngestsView, 0)]:
            with assembly_vcr.use_cassette(cassette):
                request = self.factory.post(reverse(view_str))
                response = view.as_view()(request)
                self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
                self.assertEqual(response.data['count'], count, "Only one transfer should be started")

    def request_cleanup(self):
        print('*** Requesting cleanup ***')
        with assembly_vcr.use_cassette('request_cleanup.json'):
            cleanup = CleanupRequester().run()
            self.assertNotEqual(False, cleanup)

    def run_view(self):
        with assembly_vcr.use_cassette('process_sip.json'):
            print('*** Test run view ***')
            request = self.factory.post(reverse('assemble-sip'))
            response = SIPAssemblyView.as_view()(request)
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], len(SIP.objects.filter(process_status=SIP.CREATED)), "Wrong number of objects processed")

    def cleanup_view(self):
        print('*** Test cleanup view ***')
        for sip in SIP.objects.all():
            request = self.factory.post(reverse('cleanup'), data={"identifier": sip.bag_identifier})
            response = CleanupRoutineView.as_view()(request)
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], 1, "Wrong number of objects processed")

    def request_cleanup_view(self):
        print('*** Test request cleanup view ***')
        with assembly_vcr.use_cassette('request_cleanup.json'):
            request = self.factory.post(reverse('request-cleanup'))
            response = CleanupRequestView.as_view()(request)
            self.assertEqual(response.status_code, 200, "Response error: {}".format(response.data))
            self.assertEqual(response.data['count'], len(SIP.objects.filter(process_status=SIP.APPROVED)), "Wrong number of objects processed")

    def schema(self):
        print('*** Getting schema view ***')
        schema = self.client.get(reverse('schema'))
        self.assertEqual(schema.status_code, 200, "Response error: {}".format(schema))

    def health_check(self):
        print('*** Getting status view ***')
        status = self.client.get(reverse('api_health_ping'))
        self.assertEqual(status.status_code, 200, "Response error: {}".format(status))

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
