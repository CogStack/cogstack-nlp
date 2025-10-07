import unittest
from unittest.mock import Mock, MagicMock
from typing import List

from medcat.utils.postprocessing import create_main_ann

def create_mock_entity(text: str, start_char: int, end_char: int, cui: str = None, tokens: List = None):
    """Helper function to create a mock entity with minimal setup."""
    entity = MagicMock()
    entity.base.text = text
    entity.base.start_char_index = start_char
    entity.base.end_char_index = end_char
    entity.cui = cui or "UNKNOWN"
    entity.confidence = 1.0
    entity.context_similarity = 0.0
    entity.id = id(entity)

    # Mock tokens - if no tokens provided, create empty list
    # Use side_effect to ensure __iter__ is callable and returns a new iterator each time
    if tokens:
        entity.__iter__ = Mock(side_effect=lambda: iter(tokens))
    else:
        entity.__iter__ = Mock(side_effect=lambda: iter([]))
    entity.__len__.return_value = len(tokens or [])

    return entity


def create_mock_document(text: str):
    """Helper function to create a mock document."""
    doc = MagicMock()
    doc.base.text = text
    doc.ner_ents = []
    doc.linked_ents = []
    return doc


class TestPostprocessing(unittest.TestCase):

    def setUp(self):
        # Create mock tokens for "chest pain" (if needed)
        self.token_chest = MagicMock()
        self.token_chest.base.index = 0
        self.token_pain = MagicMock()
        self.token_pain.base.index = 1

        # Create entities that overlap: "chest pain", "chest", "pain" using helper function
        self.entity_chest_pain = create_mock_entity("chest pain", 20, 30, "29857009",
                                                   [self.token_chest, self.token_pain])
        self.entity_chest = create_mock_entity("chest", 20, 25, "51185008",
                                              [self.token_chest])
        self.entity_pain = create_mock_entity("pain", 26, 30, "22253000",
                                             [self.token_pain])

        # Create document using helper function
        self.doc = create_mock_document("50M presenting with chest pain. history of T2DM.")

    def test_show_nested_entities_false_should_filter_overlaps(self):
        """Test that show_nested_entities=False should filter overlapping entities."""

        self.doc.ner_ents = [self.entity_chest_pain, self.entity_chest, self.entity_pain]

        create_main_ann(self.doc, show_nested_entities=False)

        entity_texts = [ent.base.text for ent in self.doc.linked_ents]

        # Should only keep the longest entity when show_nested_entities=False
        self.assertEqual(len(entity_texts), 1, "Should only keep one entity when filtering overlaps")
        self.assertIn("chest pain", entity_texts, "Should keep the longest entity")
        self.assertNotIn("chest", entity_texts, "Should filter out overlapping shorter entity")
        self.assertNotIn("pain", entity_texts, "Should filter out overlapping shorter entity")

    def test_show_nested_entities_true_should_keep_overlaps(self):
        """Test that show_nested_entities=True should keep all overlapping entities."""

        self.doc.ner_ents = [self.entity_chest_pain, self.entity_chest, self.entity_pain]

        create_main_ann(self.doc, show_nested_entities=True)

        entity_texts = [ent.base.text for ent in self.doc.linked_ents]

        # Should keep all entities when show_nested_entities=True
        self.assertEqual(len(entity_texts), 3, "Should keep all entities when showing nested")
        self.assertIn("chest pain", entity_texts, "Should keep the longest entity")
        self.assertIn("chest", entity_texts, "Should keep overlapping shorter entity")
        self.assertIn("pain", entity_texts, "Should keep overlapping shorter entity")

    def test_non_overlapping_entities_always_kept(self):
        """Test that non-overlapping entities are always kept regardless of config."""

        # Create a non-overlapping entity using helper function
        token_dm = MagicMock()
        token_dm.base.index = 2
        entity_dm = create_mock_entity("T2DM", 43, 47, "44054006", [token_dm])

        self.doc.ner_ents = [self.entity_chest_pain, entity_dm]

        # Test with show_nested_entities=False
        create_main_ann(self.doc, show_nested_entities=False)

        entity_texts = [ent.base.text for ent in self.doc.linked_ents]

        # Both non-overlapping entities should be kept
        self.assertEqual(len(entity_texts), 2, "Should keep all non-overlapping entities")
        self.assertIn("chest pain", entity_texts)
        self.assertIn("T2DM", entity_texts)

    def test_same_concept_multiple_locations(self):
        """Test that the same concept in different locations is kept (no character overlap)."""

        # Create two separate "chest pain" entities at different positions using helper function
        # "50F with chest pain. PMHx of T2DM and hypertension. He reported chest pain started after lunch"
        #           ^1st chest pain (20-30)                                    ^2nd chest pain (80-90)
        token_chest_1 = MagicMock()
        token_chest_1.base.index = 0
        token_pain_1 = MagicMock()
        token_pain_1.base.index = 1
        token_chest_2 = MagicMock()
        token_chest_2.base.index = 10
        token_pain_2 = MagicMock()
        token_pain_2.base.index = 11

        entity_chest_pain_1 = create_mock_entity("chest pain", 20, 30, "29857009", [token_chest_1, token_pain_1])
        entity_chest_pain_2 = create_mock_entity("chest pain", 80, 90, "29857009", [token_chest_2, token_pain_2])

        # Create overlapping entities for the first mention only
        entity_chest_1 = create_mock_entity("chest", 20, 25, "51185008", [token_chest_1])
        entity_pain_1_overlap = create_mock_entity("pain", 26, 30, "22253000", [token_pain_1])

        # Test with show_nested_entities=False
        self.doc.ner_ents = [entity_chest_pain_1, entity_chest_pain_2, entity_chest_1, entity_pain_1_overlap]

        create_main_ann(self.doc, show_nested_entities=False)

        entity_texts = [ent.base.text for ent in self.doc.linked_ents]
        entity_positions = [(ent.base.text, ent.base.start_char_index, ent.base.end_char_index)
                          for ent in self.doc.linked_ents]

        print(f"Same concept multiple locations result: {entity_positions}")

        # Should keep both "chest pain" entities (non-overlapping) but filter out overlapping shorter entities
        self.assertEqual(len(entity_texts), 2, "Should keep both non-overlapping 'chest pain' entities")
        self.assertEqual(entity_texts.count("chest pain"), 2, "Should have two 'chest pain' entities")
        self.assertNotIn("chest", entity_texts, "Should filter out overlapping 'chest' entity")
        self.assertNotIn("pain", entity_texts, "Should filter out overlapping 'pain' entity")

        # Verify positions are correct
        positions = [ent.base.start_char_index for ent in self.doc.linked_ents if ent.base.text == "chest pain"]
        self.assertIn(20, positions, "Should have 'chest pain' at position 20")
        self.assertIn(80, positions, "Should have 'chest pain' at position 80")

    def test_same_concept_multiple_locations_with_nested_true(self):
        """Test same concept in multiple locations when show_nested_entities=True."""

        # Create the same setup as above test using helper functions
        token_chest_1 = MagicMock()
        token_chest_1.base.index = 0
        token_pain_1 = MagicMock()
        token_pain_1.base.index = 1
        token_chest_2 = MagicMock()
        token_chest_2.base.index = 10
        token_pain_2 = MagicMock()
        token_pain_2.base.index = 11

        entity_chest_pain_1 = create_mock_entity("chest pain", 20, 30, "29857009", [token_chest_1, token_pain_1])
        entity_chest_pain_2 = create_mock_entity("chest pain", 80, 90, "29857009", [token_chest_2, token_pain_2])
        entity_chest_1 = create_mock_entity("chest", 20, 25, "51185008", [token_chest_1])
        entity_pain_1_overlap = create_mock_entity("pain", 26, 30, "22253000", [token_pain_1])

        # Test with show_nested_entities=True
        self.doc.ner_ents = [entity_chest_pain_1, entity_chest_pain_2, entity_chest_1, entity_pain_1_overlap]

        create_main_ann(self.doc, show_nested_entities=True)

        entity_texts = [ent.base.text for ent in self.doc.linked_ents]

        # Should keep ALL entities when show_nested_entities=True
        self.assertEqual(len(entity_texts), 4, "Should keep all entities when showing nested")
        self.assertEqual(entity_texts.count("chest pain"), 2, "Should have two 'chest pain' entities")
        self.assertIn("chest", entity_texts, "Should keep overlapping 'chest' entity")
        self.assertIn("pain", entity_texts, "Should keep overlapping 'pain' entity")


if __name__ == '__main__':
    unittest.main()