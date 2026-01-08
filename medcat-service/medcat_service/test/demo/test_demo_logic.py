"""
Unit tests for demo logic functions, specifically perform_named_entity_resolution.
"""
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
