import json
import shutil
from os import listdir, makedirs
from os.path import isdir, join
from unittest.mock import patch

import vcr
from django.test import TestCase
from django.urls import reverse
from fornax import settings
from rest_framework.test import APIRequestFactory
from sip_assembly.models import SIP
from sip_assembly.routines import (CleanupRequester, CleanupRoutine,
                                   SIPAssembler)
from sip_assembly.views import SIPViewSet

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

    def test_create_rights_csv(self):
        with open(join(csv_fixture_dir, "{}.json".format("aurora_example")), 'r') as json_file:
            json_data = json.load(json_file)
        created_csv = CsvCreator("1.11.2").create_rights_csv(
            join(self.tmp_dir, "aurora_example"),
            json_data["bag_data"]["rights_statements"])
        self.assertEqual(
            created_csv, "CSV {} created.".format(join(self.tmp_dir, 'aurora_example', 'data', 'metadata', 'rights.csv')))

    def test_get_rights_rows(self):
        for am_version in ["1.12", "1.13.1"]:
            csv_creator = CsvCreator(am_version)
            csv_creator.bag_path = join(self.tmp_dir, 'digitization_example')
            with open(join(csv_fixture_dir, "{}.json".format("digitization_example")), 'r') as json_file:
                json_data = json.load(json_file)
            csv_creator.rights_statements = json_data["bag_data"]["rights_statements"]
            rights_rows = csv_creator.get_rights_rows(join(self.tmp_dir, 'digitization_example', 'data', 'objects'), "sample.txt")
            if am_version == "1.13.1":
                self.assertEqual(len(rights_rows), 2)
            elif am_version == "1.12":
                self.assertEqual(len(rights_rows), 1)
            for row in rights_rows:
                self.assertEqual(len(row), 18)

    def tearDown(self):
        if isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)


class SIPAssemblyTest(TestCase):

    # TODO: replace this with fixtures
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
        for f in listdir(data_fixture_dir):
            with open(join(data_fixture_dir, f), 'r') as json_file:
                aurora_data = json.load(json_file)
            request = self.factory.post(reverse('sip-list'), aurora_data, format='json')
            response = SIPViewSet.as_view(actions={"post": "create"})(request)
            self.assertEqual(response.data["bag_identifier"], aurora_data["identifier"])
            self.assertEqual(response.data["origin"], aurora_data["origin"])
            self.assertEqual(response.data["data"], aurora_data["bag_data"])
            self.assertEqual(response.status_code, 201, "Wrong HTTP code")
        self.assertEqual(len(SIP.objects.all()), len(listdir(data_fixture_dir)), "Incorrect number of SIPs created")
        return SIP.objects.all()

    def process_sip(self):
        with assembly_vcr.use_cassette('process_sip.json'):
            assembly = SIPAssembler().run()
            self.assertNotEqual(False, assembly)

    def cleanup_sip(self):
        for sip in SIP.objects.all():
            CleanupRoutine(
                sip.bag_identifier).run()
        self.assertEqual(0, len(listdir(self.dest_dir)))

    def request_cleanup(self):
        with assembly_vcr.use_cassette('request_cleanup.json'):
            cleanup = CleanupRequester().run()
            self.assertNotEqual(False, cleanup)

    def test_sips(self):
        sips = self.create_sip()
        for sip in sips:
            sip.bag_path = join(
                self.src_dir, "{}.tar.gz".format(
                    sip.bag_identifier))
            sip.save()
        self.process_sip()
        self.cleanup_sip()
        self.request_cleanup()

    def tearDown(self):
        for d in [self.src_dir, self.tmp_dir, self.dest_dir]:
            if isdir(d):
                shutil.rmtree(d)


class ViewTests(TestCase):
    """Tests views."""

    def setUp(self):
        self.factory = APIRequestFactory()

    def assert_status_code(self, method, url, status_code, data=None):
        """Asserts that a request returns the expected HTTP status_code."""
        response = getattr(self.client, method)(url, data, content_type="application/json")
        self.assertEqual(
            response.status_code, status_code,
            f"Unexpected status code {response.status_code} for url {url}")
        return response

    def test_create_sip_view(self):
        for f in listdir(data_fixture_dir):
            with open(join(data_fixture_dir, f), 'r') as json_file:
                source_data = json.load(json_file)
                response = self.assert_status_code("post", reverse("sip-list"), 201, data=source_data)
                self.assertEqual(response.data["bag_identifier"], source_data["identifier"])
                self.assertEqual(response.data["origin"], source_data["origin"])
                self.assertEqual(response.data["data"], source_data["bag_data"])
                self.assertEqual(response.data["process_status"], SIP.CREATED)
                self.assertEqual(response.data["bag_path"], join(
                    settings.BASE_DIR,
                    settings.SRC_DIR,
                    f"{source_data['identifier']}.tar.gz"))

    @patch('sip_assembly.routines.SIPActions.create_package')
    def test_archivematica_create_view(self, mock_create):
        """Tests view which creates a package in Archivematica."""
        self.assert_status_code("post", reverse("create-transfer"), 200)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_count, 1)

    @patch('sip_assembly.routines.SIPActions.remove_completed')
    def test_archivematica_close_transfer_view(self, mock_remove):
        """Tests view which closes transfers in Archivematica"""
        self.assert_status_code("post", reverse("remove-transfers"), 200)
        mock_remove.assert_called_once()
        mock_remove.assert_called_with('transfers')

    @patch('sip_assembly.routines.SIPActions.remove_completed')
    def test_archivematica_close_ingests_view(self, mock_remove):
        """Tests view which closes ingests in Archivematica"""
        self.assert_status_code("post", reverse("remove-ingests"), 200)
        mock_remove.assert_called_once()
        mock_remove.assert_called_with('ingests')

    @patch('sip_assembly.routines.SIPAssembler.__init__')
    @patch('sip_assembly.routines.SIPAssembler.run')
    def test_sip_assembly_view(self, mock_assemble, mock_init):
        """Tests the SIPAssemblyView."""
        mock_init.return_value = None
        self.assert_status_code("post", reverse("assemble-sip"), 200)
        mock_assemble.assert_called_once()

    @patch('sip_assembly.routines.CleanupRoutine.__init__')
    @patch('sip_assembly.routines.CleanupRoutine.run')
    def test_cleanup_view(self, mock_cleanup, mock_init):
        """Tests the CleanupRoutineView."""
        mock_init.return_value = None
        identifier = "12345"
        self.assert_status_code("post", reverse("cleanup"), 200, {"identifier": identifier})
        mock_cleanup.assert_called_once()
        mock_init.assert_called_with(identifier)

    @patch('sip_assembly.routines.CleanupRequester.run')
    def test_request_cleanup_view(self, mock_request):
        """Tests the CleanupRequestView."""
        self.assert_status_code("post", reverse("request-cleanup"), 200)
        mock_request.assert_called_once()

    def test_schema_view(self):
        """Tests the OpenAPI schema view."""
        self.assert_status_code("get", reverse("schema"), 200)

    def test_health_check_view(self):
        """Tests the health check view."""
        self.assert_status_code("get", reverse("api_health_ping"), 200)
