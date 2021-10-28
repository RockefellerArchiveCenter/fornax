import json
import random
import shutil
import tarfile
from os import listdir, makedirs
from os.path import basename, isdir, isfile, join
from unittest.mock import patch

import bagit
from django.test import TestCase
from django.urls import reverse
from fornax import settings

from .csv_creator import CsvCreator
from .models import SIP
from .routines import (CleanupRequester, CleanupRoutine, SIPActions,
                       SIPAssembler)
from .routines_helpers import extract_all

data_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'json')
bag_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'bags')
csv_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'csv_creation')


class CsvCreatorTests(TestCase):
    """Tests CSV creation."""

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


class RoutineTests(TestCase):
    """Tests the routines."""

    fixtures = ["fixtures/initial.json"]

    def setUp(self):
        if isdir(settings.SRC_DIR):
            shutil.rmtree(settings.SRC_DIR)
        shutil.copytree(bag_fixture_dir, settings.SRC_DIR)
        for dir in [settings.TMP_DIR, settings.DEST_DIR]:
            if not isdir(dir):
                makedirs(dir)

    def set_process_status(self, status):
        for sip in SIP.objects.all():
            sip.process_status = status
            sip.save()

    def assert_files_not_removed(self, sip):
        """Asserts that existing files are not preserved and moved to the correct directory."""
        source_tar = tarfile.open(join(bag_fixture_dir, f"{sip.bag_identifier}.tar.gz"))
        processed_tar = tarfile.open(join(settings.DEST_DIR, f"{sip.bag_identifier}.tar.gz"))
        source_members = source_tar.getnames()
        processed_members = processed_tar.getnames()
        for source_dir, processed_dir in [
                (f"{sip.bag_identifier}/data/metadata/submissionDocumentation/", f"{sip.bag_identifier}/data/objects/metadata/submissionDocumentation/"),
                (f"{sip.bag_identifier}/objects/", f"{sip.bag_identifier}/data/objects/")]:
            source_files = [basename(m) for m in source_members if source_dir in m]
            processed_files = [basename(p) for p in processed_members if processed_dir in p]
            self.assertTrue(all([f in processed_files for f in source_files]))

    @patch("sip_assembly.routines.AMClient.get_processing_config")
    @patch("asterism.file_helpers.remove_file_or_dir")
    def test_process_sip(self, mock_remove_file_or_dir, mock_processing_config):
        self.set_process_status(SIP.CREATED)
        with open(join("processing_configs", "processingMCP.xml"), "r") as config_file:
            config_contents = config_file.read()
        mock_processing_config.return_value = config_contents
        message, sip_ids = SIPAssembler().run()
        self.assertEqual(message, "All SIPs assembled.")
        self.assertEqual(len(sip_ids), len(SIP.objects.all()))
        for sip in SIP.objects.all():
            self.assertEqual(sip.process_status, SIP.ASSEMBLED)
            self.assertEqual(join(settings.DEST_DIR, f"{sip.bag_identifier}.tar.gz"), sip.bag_path)
            self.assertTrue(isfile(sip.bag_path))
            self.assert_files_not_removed(sip)
        for sip_path in listdir(settings.DEST_DIR):
            sip_identifier = sip_path.split(".")[0]
            extracted_path = extract_all(join(settings.DEST_DIR, sip_path), sip_identifier, settings.DEST_DIR)
            self.assertTrue(isfile(join(extracted_path, "processingMCP.xml")))
            bag = bagit.Bag(extracted_path)
            self.assertEqual(sip_identifier, bag.info["Internal-Sender-Identifier"])

        self.set_process_status(SIP.CREATED)
        mock_processing_config.side_effect = Exception()
        with self.assertRaises(Exception) as e:
            SIPAssembler().run()
        self.assertIn("Error assembling SIP", str(e.exception))
        self.assertEqual(mock_remove_file_or_dir.call_count, 2)

    def test_cleanup_sip(self):
        """Asserts that the CleanupRoutine removes binaries and does not throw
        an exception if a bag has already been cleaned up."""
        shutil.rmtree(settings.DEST_DIR)
        shutil.copytree(bag_fixture_dir, settings.DEST_DIR)
        for sip in SIP.objects.all():
            message, _ = CleanupRoutine(sip.bag_identifier).run()
            self.assertEqual(message, "Transfer removed.")
        self.assertEqual(0, len(listdir(settings.DEST_DIR)))
        for sip in SIP.objects.all():
            message, _ = CleanupRoutine(sip.bag_identifier).run()
            self.assertEqual(message, "Transfer was not found.")

    @patch("sip_assembly.routines.requests.post")
    def test_request_cleanup(self, mock_post):
        """Asserts that the CleanupRequester returns expected values and handles exceptions."""
        self.set_process_status(SIP.APPROVED)
        mock_post.return_value.status_code = 200
        message, sip_ids = CleanupRequester().run()
        self.assertEqual(message, "Requests sent to clean up SIPs.")
        self.assertEqual(len(sip_ids), len(SIP.objects.all()))
        self.assertTrue(all([s.process_status == SIP.CLEANED_UP for s in SIP.objects.all()]))

        self.set_process_status(SIP.APPROVED)
        mock_post.return_value.status_code = 400
        reason = "foobar"
        mock_post.return_value.reason = reason
        with self.assertRaises(Exception) as e:
            message, sip_ids = CleanupRequester().run()
        self.assertIn(reason, str(e.exception))

    @patch("sip_assembly.routines.AMClient.get_unit_status")
    @patch("sip_assembly.routines.AMClient.create_package")
    def test_create_package(self, mock_create, mock_status):
        """Asserts packge is successfully created if another package is not
        processing in Archivematica."""
        self.set_process_status(SIP.ASSEMBLED)
        mock_create.return_value = {"id": "12345"}
        mock_status.return_value = "STORED"
        message, sip_ids = SIPActions().create_package()
        self.assertEqual(message, "Transfer started")
        self.assertEqual(sip_ids, ["12345"])
        mock_create.assert_called_once()
        mock_create.assert_called_with()

        self.set_process_status(SIP.ASSEMBLED)
        last_started = random.choice(SIP.objects.all())
        last_started.process_status = SIP.APPROVED
        last_started.save()
        mock_status.return_value = "PROCESSING"
        message, sip_ids = SIPActions().create_package()
        self.assertEqual(message, "Another transfer is processing, waiting until it finishes.")
        self.assertEqual(sip_ids, None)

    @patch("sip_assembly.routines.AMClient.close_completed_transfers")
    @patch("sip_assembly.routines.AMClient.close_completed_ingests")
    def test_remove_completed(self, mock_close_ingests, mock_close_transfers):
        """Asserts completed transfers and ingests are closed and exceptions are handled."""
        mock_close_ingests.return_value = {}
        mock_close_transfers.return_value = {}

        SIPActions().remove_completed("transfers")
        self.assertEqual(mock_close_transfers.call_count, 3)

        SIPActions().remove_completed("ingests")
        self.assertEqual(mock_close_ingests.call_count, 3)

        mock_close_ingests.return_value = {"close_failed": "12345"}
        with self.assertRaises(Exception) as e:
            SIPActions().remove_completed("ingests")
        self.assertIn("Error removing ingests from Archivematica dashboard", str(e.exception))
        self.assertIn("12345", str(e.exception))

    def tearDown(self):
        for d in [settings.SRC_DIR, settings.TMP_DIR, settings.DEST_DIR]:
            if isdir(d):
                shutil.rmtree(d)


class ViewTests(TestCase):
    """Tests views."""

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
