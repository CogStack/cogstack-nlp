"""
Unit tests for demo logic functions, specifically perform_named_entity_resolution.
"""
import json
import unittest
from unittest.mock import MagicMock, patch

from medcat_service.config import Settings
from medcat_service.demo.demo_logic import EntityResponse, perform_named_entity_resolution
from medcat_service.nlp_processor import MedCatProcessor
from medcat_service.test.common import (
    get_example_long_document,
    get_example_short_document,
    setup_medcat_processor,
)


class TestDemoLogic(unittest.TestCase):
    """
    Test cases for demo logic functions.
    """

    processor: MedCatProcessor

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once before all test methods."""
        setup_medcat_processor()
        cls.processor = MedCatProcessor(Settings())

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_text = get_example_short_document()

    @patch("medcat_service.demo.demo_logic.get_settings")
    @patch("medcat_service.demo.demo_logic.get_medcat_processor")
    def test_perform_named_entity_resolution_with_valid_text(self, mock_get_processor, mock_get_settings):
        """Test perform_named_entity_resolution with valid input text."""
        # Setup mocks
        mock_get_settings.return_value = Settings()
        mock_get_processor.return_value = TestDemoLogic.processor

        # Execute
        result_dict, result_table = perform_named_entity_resolution(self.test_text)

        # Assert
        self.assertIsNotNone(result_dict)
        self.assertIsNotNone(result_table)
        assert result_dict is not None  # Type narrowing for type checker
        assert result_table is not None  # Type narrowing for type checker
        self.assertIn("text", result_dict)
        self.assertIn("entities", result_dict)
        self.assertEqual(result_dict["text"], self.test_text)
        self.assertIsInstance(result_dict["entities"], list)
        self.assertIsInstance(result_table, list)

    @patch("medcat_service.demo.demo_logic.get_settings")
    @patch("medcat_service.demo.demo_logic.get_medcat_processor")
    def test_perform_named_entity_resolution_with_empty_string(self, mock_get_processor, mock_get_settings):
        """Test perform_named_entity_resolution with empty string."""
        # Setup mocks
        mock_get_settings.return_value = Settings()
        mock_get_processor.return_value = TestDemoLogic.processor

        # Execute
        result_dict, result_table = perform_named_entity_resolution("")

        # Assert
        self.assertIsNone(result_dict)
        self.assertIsNone(result_table)

    @patch("medcat_service.demo.demo_logic.get_settings")
    @patch("medcat_service.demo.demo_logic.get_medcat_processor")
    def test_perform_named_entity_resolution_with_whitespace_only(self, mock_get_processor, mock_get_settings):
        """Test perform_named_entity_resolution with whitespace-only string."""
        # Setup mocks
        mock_get_settings.return_value = Settings()
        mock_get_processor.return_value = TestDemoLogic.processor

        # Execute
        result_dict, result_table = perform_named_entity_resolution("   \n\t  ")

        # Assert
        self.assertIsNone(result_dict)
        self.assertIsNone(result_table)

    @patch("medcat_service.demo.demo_logic.get_settings")
    @patch("medcat_service.demo.demo_logic.get_medcat_processor")
    def test_perform_named_entity_resolution_response_structure(self, mock_get_processor, mock_get_settings):
        """Test that the response has the correct structure."""
        # Setup mocks
        mock_get_settings.return_value = Settings()
        mock_get_processor.return_value = TestDemoLogic.processor

        # Execute
        result_dict, result_table = perform_named_entity_resolution(self.test_text)

        # Assert structure
        self.assertIsNotNone(result_dict)
        assert result_dict is not None  # Type narrowing for type checker
        self.assertIn("text", result_dict)
        self.assertIn("entities", result_dict)
        self.assertEqual(result_dict["text"], self.test_text)

        # Check entity structure if entities exist
        if result_dict["entities"]:
            entity = result_dict["entities"][0]
            self.assertIn("entity", entity)
            self.assertIn("score", entity)
            self.assertIn("index", entity)
            self.assertIn("word", entity)
            self.assertIn("start", entity)
            self.assertIn("end", entity)

    @patch("medcat_service.demo.demo_logic.get_settings")
    @patch("medcat_service.demo.demo_logic.get_medcat_processor")
    def test_perform_named_entity_resolution_table_format(self, mock_get_processor, mock_get_settings):
        """Test that the table format is correct."""
        # Setup mocks
        mock_get_settings.return_value = Settings()
        mock_get_processor.return_value = TestDemoLogic.processor

        # Execute
        result_dict, result_table = perform_named_entity_resolution(self.test_text)

        # Assert table structure
        self.assertIsNotNone(result_table)
        self.assertIsInstance(result_table, list)
        # If there are annotations, check the structure
        if result_table:
            self.assertIsInstance(result_table[0], list)
            # Should have 6 columns based on headers
            if result_table[0]:
                self.assertEqual(len(result_table[0]), 6)

    @patch("medcat_service.demo.demo_logic.get_settings")
    @patch("medcat_service.demo.demo_logic.get_medcat_processor")
    def test_perform_named_entity_resolution_with_long_text(self, mock_get_processor, mock_get_settings):
        """Test perform_named_entity_resolution with longer text."""
        # Setup mocks
        mock_get_settings.return_value = Settings()
        mock_get_processor.return_value = TestDemoLogic.processor

        long_text = get_example_long_document()

        # Execute
        result_dict, result_table = perform_named_entity_resolution(long_text)

        # Assert
        self.assertIsNotNone(result_dict)
        self.assertIsNotNone(result_table)
        assert result_dict is not None  # Type narrowing for type checker
        self.assertEqual(result_dict["text"], long_text)

    @patch("medcat_service.demo.demo_logic.get_settings")
    @patch("medcat_service.demo.demo_logic.get_medcat_processor")
    def test_perform_named_entity_resolution_returns_entity_response_format(
        self, mock_get_processor, mock_get_settings
    ):
        """Test that the result can be validated as EntityResponse format."""
        # Setup mocks
        mock_get_settings.return_value = Settings()
        mock_get_processor.return_value = TestDemoLogic.processor

        # Execute
        result_dict, result_table = perform_named_entity_resolution(self.test_text)

        # Assert - validate the dict can be converted to EntityResponse
        self.assertIsNotNone(result_dict)
        assert result_dict is not None  # Type narrowing for type checker
        try:
            response = EntityResponse(**result_dict)
            self.assertEqual(response.text, self.test_text)
            self.assertIsInstance(response.entities, list)
        except Exception as e:
            self.fail(f"Result dict should be valid EntityResponse format: {e}")

    @patch("medcat_service.demo.demo_logic.get_settings")
    @patch("medcat_service.demo.demo_logic.get_medcat_processor")
    def test_perform_named_entity_resolution_with_mocked_get_entities(
        self, mock_get_processor, mock_get_settings
    ):
        """Test perform_named_entity_resolution with mocked get_entities returning JSON data."""
        # Mock entities data inline as JSON string
        mock_annotations_json = """
        {
          "annotations": [
            {
              "1": {
                "pretty_name": "Cerebral Hemorrhage",
                "cui": "C2937358",
                "type_ids": [
                  "T046"
                ],
                "source_value": "Intracerebral hemorrhage",
                "detected_name": "intracerebral~hemorrhage",
                "acc": 1,
                "context_similarity": 1,
                "start": 13,
                "end": 37,
                "id": 1,
                "meta_anns": {
                  "Status": {
                    "value": "Affirmed",
                    "confidence": 0.9999077320098877,
                    "name": "Status"
                  }
                },
                "context_left": [],
                "context_center": [],
                "context_right": [],
                "icd10": [
                  {
                    "chapter": "I61",
                    "name": "Intracerebral haemorrhage"
                  },
                  {
                    "chapter": "I61.9",
                    "name": "Intracerebral haemorrhage, unspecified"
                  }
                ],
                "snomed": [
                  "S-1508000",
                  "S-155389003",
                  "S-155391006",
                  "S-155394003",
                  "S-195163003",
                  "S-195173001",
                  "S-266313001",
                  "S-274100004"
                ]
              }
            }
          ]
        }
        """
        mock_annotations_data = json.loads(mock_annotations_json)

        # Create a mock processor
        mock_processor = MagicMock(spec=MedCatProcessor)

        # Mock process_content to return a ProcessResult with the expected structure
        from medcat_service.types import ProcessResult

        mock_process_result = ProcessResult(
            text=self.test_text,
            annotations=mock_annotations_data["annotations"],
            success=True,
            timestamp="2024-01-01T00:00:00Z",
            elapsed_time=0.1,
        )
        mock_processor.process_content.return_value = mock_process_result

        # Setup mocks
        mock_get_settings.return_value = Settings()
        mock_get_processor.return_value = mock_processor

        # Expected result as JSON string for readability
        expected = json.dumps(
            {
                "text": self.test_text,
                "entities": [
                    {
                        "entity": "C2937358",
                        "score": 1.0,
                        "index": 1,
                        "word": "intracerebral~hemorrhage",
                        "start": 13,
                        "end": 37,
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )

        # Execute
        actual_dict, result_table = perform_named_entity_resolution(self.test_text)

        # Assert
        self.assertIsNotNone(actual_dict)
        assert actual_dict is not None  # Type narrowing for type checker
        actual = json.dumps(actual_dict, indent=2, sort_keys=True)
        self.assertEqual(expected, actual)

        # Verify process_content was called with correct input
        mock_processor.process_content.assert_called_once()
        call_args = mock_processor.process_content.call_args[0][0]
        self.assertEqual(call_args["text"], self.test_text)


if __name__ == "__main__":
    unittest.main()
