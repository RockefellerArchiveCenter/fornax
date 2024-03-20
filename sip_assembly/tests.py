import json
import random
import shutil
import tarfile
from os import listdir, makedirs
from os.path import basename, isdir, isfile, join
from unittest.mock import patch

import bagit
from amclient import errors, utils
from django.test import TestCase
from django.urls import reverse

from fornax import settings

from .csv_creator import CsvCreator
from .models import SIP
from .routines import (ArchivematicaClientMixin, AssemblePackageRoutine,
                       BaseRoutine, CleanupPackageRequester,
                       CleanupPackageRoutine, ExtractPackageRoutine,
                       RemoveCompletedIngestsRoutine,
                       RemoveCompletedTransfersRoutine,
                       RestructurePackageRoutine, StartPackageRoutine)

data_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'json')
bag_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'bags')
csv_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'csv_creation')
processing_config_fixture_dir = join(settings.BASE_DIR, 'fixtures', 'processing_configs')


class CsvCreatorTests(TestCase):
    """Tests CSV creation."""

    def setUp(self):
        self.tmp_dir = settings.TMP_DIR
        if isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)
        makedirs(self.tmp_dir)
        for directory in ['aurora_example', 'digitization_example']:
            shutil.copytree(join(csv_fixture_dir, directory), join(self.tmp_dir, directory))

    @patch('amclient.AMClient.validate_csv')
    def test_create_rights_csv(self, mock_validate):
        mock_validate.return_value = {"valid": "true"}
        with open(join(csv_fixture_dir, "{}.json".format("aurora_example")), 'r') as json_file:
            json_data = json.load(json_file)
        created_csv = CsvCreator("1.11.2", ArchivematicaClientMixin().get_client("aurora")).create_rights_csv(
            join(self.tmp_dir, "aurora_example"),
            json_data["bag_data"]["rights_statements"])
        self.assertEqual(
            created_csv, "CSV {} created.".format(join(self.tmp_dir, 'aurora_example', 'data', 'metadata', 'rights.csv')))

    @patch('amclient.AMClient.validate_csv')
    def test_get_rights_rows(self, mock_validate):
        for am_version in ["1.12", "1.13.1"]:
            mock_validate.return_value = {"valid": "true"}
            csv_creator = CsvCreator(am_version, ArchivematicaClientMixin().get_client("digitization"))
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

    @patch('amclient.AMClient.validate_csv')
    def test_invalid_csv(self, mock_validate):
        message = "error message for invalid CSV."
        mock_validate.return_value = utils.Error(errors.ERR_INVALID_RESPONSE, message=message)
        with open(join(csv_fixture_dir, "{}.json".format("aurora_example")), 'r') as json_file:
            json_data = json.load(json_file)
        with self.assertRaises(Exception) as err:
            CsvCreator("1.11.2", ArchivematicaClientMixin().get_client("aurora")).create_rights_csv(
                join(self.tmp_dir, "aurora_example"),
                json_data["bag_data"]["rights_statements"])
        self.assertIn(message, str(err.exception))

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
        source_members = source_tar.getnames()
        for source_dir, processed_dir in [
                (f"{sip.bag_identifier}/data/metadata/submissionDocumentation/", f"{sip.bag_identifier}/data/objects/metadata/submissionDocumentation/"),
                (f"{sip.bag_identifier}/objects/", f"{sip.bag_identifier}/data/objects/")]:
            source_files = [basename(m) for m in source_members if source_dir in m]
            if source_files:
                processed_files = [basename(p) for p in listdir(join(settings.TMP_DIR, processed_dir))]
                self.assertTrue(all([f in processed_files for f in source_files]))

    @patch("sip_assembly.routines.BaseRoutine.process_sip")
    def test_base_routine(self, mock_process):
        """Assert BaseRoutine delivers expected messages and raises expected exceptions."""
        expected_success_message = "foo"
        expected_idle_message = "bar"
        expected_exception = "baz"
        mock_process.return_value = expected_success_message
        self.set_process_status(SIP.CREATED)
        routine = BaseRoutine()
        routine.start_status = SIP.CREATED
        routine.in_process_status = SIP.ASSEMBLING
        routine.end_status = SIP.ASSEMBLED
        routine.idle_message = expected_idle_message

        message, sip_id = routine.run()
        self.assertEqual(message, expected_success_message)
        self.assertEqual(len(sip_id), 1)

        routine.start_status = SIP.APPROVED
        message, sip_id = routine.run()
        self.assertEqual(message, expected_idle_message)
        self.assertEqual(sip_id, None)

        routine.start_status = SIP.CREATED
        mock_process.side_effect = Exception(expected_exception)
        with self.assertRaises(Exception) as exc:
            message, sip_id = routine.run()
        self.assertIn(expected_exception, str(exc.exception))

    def test_extract_sip(self):
        """Asserts the ExtractPackageRoutine extracts the package and sets the bag_path."""
        self.set_process_status(SIP.CREATED)
        message, sip_id = ExtractPackageRoutine().run()
        self.assertEqual(message, "SIP extracted.")
        self.assertEqual(len(sip_id), 1)
        for sip in SIP.objects.filter(process_status=SIP.ASSEMBLED):
            self.assertTrue(isdir(sip.bag_path))
            self.assertEqual(sip.bag_path, join(settings.TMP_DIR, sip.bag_identifier))

    @patch("sip_assembly.routines.AMClient.get_processing_config")
    @patch('amclient.AMClient.validate_csv')
    def test_restructure_sip(self, mock_validate, mock_processing_config):
        """Asserts the RestructurePackageRoutine adds expected data and does not replace files."""
        with open(join(processing_config_fixture_dir, "processingMCP.xml"), "r") as config_file:
            config_contents = config_file.read()
        mock_processing_config.return_value = config_contents
        mock_validate.return_value = {"valid": "true"}
        self.set_process_status(SIP.CREATED)
        total_sips = len(SIP.objects.all())
        extracted = 0
        while extracted < total_sips:
            ExtractPackageRoutine().run()
            extracted += 1
        restructured = 0
        while restructured < total_sips:
            message, sip_id = RestructurePackageRoutine().run()
            self.assertEqual(message, "SIP restructured.")
            self.assertEqual(len(sip_id), 1)
            restructured += 1
        for sip in SIP.objects.filter(process_status=SIP.RESTRUCTURED):
            bag = bagit.Bag(sip.bag_path)
            self.assertEqual(sip.bag_identifier, bag.info["Internal-Sender-Identifier"])
            self.assertTrue(isfile(join(sip.bag_path, "processingMCP.xml")))
            self.assert_files_not_removed(sip)

    def test_assemble_sip(self):
        """Asserts that the AssemblePackageView creates the expected tarfile."""
        self.set_process_status(SIP.CREATED)
        ExtractPackageRoutine().run()
        self.set_process_status(SIP.RESTRUCTURED)
        message, sip_id = AssemblePackageRoutine().run()
        self.assertEqual(message, "SIP assembled.")
        self.assertEqual(len(sip_id), 1)
        for sip in SIP.objects.filter(process_status=SIP.ASSEMBLED):
            self.assertEqual(join(settings.DEST_DIR, f"{sip.bag_identifier}.tar.gz"), sip.bag_path)
            self.assertTrue(isfile(sip.bag_path))

    def test_cleanup_sip(self):
        """Asserts that the CleanupPackageRoutine removes binaries and does not throw
        an exception if a bag has already been cleaned up."""
        shutil.rmtree(settings.DEST_DIR)
        shutil.copytree(bag_fixture_dir, settings.DEST_DIR)
        for sip in SIP.objects.all():
            message, _ = CleanupPackageRoutine(sip.bag_identifier).run()
            self.assertEqual(message, "Transfer removed.")
        self.assertEqual(0, len(listdir(settings.DEST_DIR)))
        for sip in SIP.objects.all():
            message, _ = CleanupPackageRoutine(sip.bag_identifier).run()
            self.assertEqual(message, "Transfer was not found.")

    @patch("sip_assembly.routines.requests.post")
    def test_request_cleanup(self, mock_post):
        """Asserts that the CleanupPackageRequester returns expected values and handles exceptions."""
        self.set_process_status(SIP.APPROVED)
        mock_post.return_value.status_code = 200
        message, sip_id = CleanupPackageRequester().run()
        sip = SIP.objects.get(bag_identifier=sip_id[0])
        self.assertEqual(message, "Request sent to clean up SIP.")
        self.assertEqual(len(sip_id), 1)
        self.assertEqual(sip.process_status, SIP.CLEANED_UP)

        self.set_process_status(SIP.APPROVED)
        mock_post.return_value.status_code = 400
        reason = "foobar"
        mock_post.return_value.reason = reason
        with self.assertRaises(Exception) as e:
            message, _ = CleanupPackageRequester().run()
        self.assertIn(reason, str(e.exception))

    @patch("sip_assembly.routines.AMClient.get_unit_status")
    @patch("sip_assembly.routines.AMClient.create_package")
    def test_create_package(self, mock_create, mock_status):
        """Asserts package is successfully created if another package is not processing in Archivematica."""
        self.set_process_status(SIP.ASSEMBLED)
        mock_create.return_value = {"id": "12345"}
        mock_status.return_value = {'type': 'transfer', 'path': '/var/archivematica/sharedDirectory/currentlyProcessing/59193ace-30c3-4a3b-a656-9232ebc7ce0e.tar.gz', 'directory': '59193ace-30c3-4a3b-a656-9232ebc7ce0e.tar.gz', 'name': '59193ace-30c3-4a3b-a656-9232ebc7ce0e.tar.gz', 'uuid': '1651add2-d21b-445a-abd4-444450648ba9', 'microservice': 'Extract zipped bag transfer', 'status': 'STORED', 'message': 'Fetched status for 1651add2-d21b-445a-abd4-444450648ba9 successfully.'}
        message, sip_id = StartPackageRoutine().run()
        sip = SIP.objects.get(bag_identifier=sip_id[0])
        self.assertEqual(message, "Transfer started.")
        self.assertEqual(len(sip_id), 1)
        mock_create.assert_called_once()
        self.assertEqual(sip.process_status, SIP.APPROVED)

        self.set_process_status(SIP.ASSEMBLED)
        last_started = random.choice(SIP.objects.all())
        last_started.process_status = SIP.APPROVED
        last_started.archivematica_uuid = "12345"
        last_started.save()
        mock_status.return_value = {'type': 'transfer', 'path': '/var/archivematica/sharedDirectory/currentlyProcessing/59193ace-30c3-4a3b-a656-9232ebc7ce0e.tar.gz', 'directory': '59193ace-30c3-4a3b-a656-9232ebc7ce0e.tar.gz', 'name': '59193ace-30c3-4a3b-a656-9232ebc7ce0e.tar.gz', 'uuid': '1651add2-d21b-445a-abd4-444450648ba9', 'microservice': 'Extract zipped bag transfer', 'status': 'PROCESSING', 'message': 'Fetched status for 1651add2-d21b-445a-abd4-444450648ba9 successfully.'}
        message, sip_id = StartPackageRoutine().run()
        sip = SIP.objects.get(bag_identifier=sip_id[0])
        self.assertEqual(message, "Another transfer is processing, waiting until it finishes.")
        self.assertEqual(len(sip_id), 1)
        self.assertEqual(sip.process_status, SIP.ASSEMBLED)

    @patch("sip_assembly.routines.AMClient.close_completed_transfers")
    @patch("sip_assembly.routines.AMClient.close_completed_ingests")
    def test_remove_completed(self, mock_close_ingests, mock_close_transfers):
        """Asserts completed transfers and ingests are closed and exceptions are handled."""
        mock_close_ingests.return_value = {}
        mock_close_transfers.return_value = {}

        RemoveCompletedTransfersRoutine().run()
        self.assertEqual(mock_close_transfers.call_count, 4)

        RemoveCompletedIngestsRoutine().run()
        self.assertEqual(mock_close_ingests.call_count, 4)

        mock_close_ingests.return_value = {"close_failed": "12345"}
        with self.assertRaises(Exception) as e:
            RemoveCompletedIngestsRoutine().run()
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

    @patch('sip_assembly.routines.StartPackageRoutine.run')
    def test_archivematica_create_view(self, mock_create):
        """Tests view which creates a package in Archivematica."""
        self.assert_status_code("post", reverse("start-sip"), 200)
        mock_create.assert_called_once()
        self.assertEqual(mock_create.call_count, 1)

    @patch('sip_assembly.routines.RemoveCompletedTransfersRoutine.run')
    def test_archivematica_close_transfer_view(self, mock_remove):
        """Tests view which closes transfers in Archivematica"""
        self.assert_status_code("post", reverse("remove-transfers"), 200)
        mock_remove.assert_called_once()

    @patch('sip_assembly.routines.RemoveCompletedIngestsRoutine.run')
    def test_archivematica_close_ingests_view(self, mock_remove):
        """Tests view which closes ingests in Archivematica"""
        self.assert_status_code("post", reverse("remove-ingests"), 200)
        mock_remove.assert_called_once()

    @patch('sip_assembly.routines.ExtractPackageRoutine.__init__')
    @patch('sip_assembly.routines.ExtractPackageRoutine.run')
    def test_extract_sip_view(self, mock_extract, mock_init):
        """Tests view which extracts SIPs"""
        mock_init.return_value = None
        self.assert_status_code("post", reverse("extract-sip"), 200)
        mock_extract.assert_called_once()

    @patch('sip_assembly.routines.RestructurePackageRoutine.__init__')
    @patch('sip_assembly.routines.RestructurePackageRoutine.run')
    def test_restructure_sip_view(self, mock_restructure, mock_init):
        """Tests view restructures SIPs"""
        mock_init.return_value = None
        self.assert_status_code("post", reverse("restructure-sip"), 200)
        mock_restructure.assert_called_once()

    @patch('sip_assembly.routines.AssemblePackageRoutine.run')
    def test_assemble_sip_view(self, mock_assemble):
        """Tests view which assembles a SIP tarfile."""
        self.assert_status_code("post", reverse("assemble-sip"), 200)
        mock_assemble.assert_called_once()

    @patch('sip_assembly.routines.CleanupPackageRoutine.__init__')
    @patch('sip_assembly.routines.CleanupPackageRoutine.run')
    def test_cleanup_view(self, mock_cleanup, mock_init):
        """Tests the CleanupRoutineView."""
        mock_init.return_value = None
        identifier = "12345"
        self.assert_status_code("post", reverse("cleanup-sip"), 200, {"identifier": identifier})
        mock_cleanup.assert_called_once()
        mock_init.assert_called_with(identifier)

    @patch('sip_assembly.routines.CleanupPackageRequester.run')
    def test_request_cleanup_view(self, mock_request):
        """Tests the CleanupRequestView."""
        self.assert_status_code("post", reverse("request-cleanup"), 200)
        mock_request.assert_called_once()

    def test_health_check_view(self):
        """Tests the health check view."""
        self.assert_status_code("get", reverse("ping"), 200)
