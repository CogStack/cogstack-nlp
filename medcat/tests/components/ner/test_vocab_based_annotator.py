from collections import defaultdict

from medcat.components.ner import vocab_based_annotator
from medcat.tokenizing.tokenizers import create_tokenizer
from medcat.config import Config

import unittest
import unittest.mock


class MaybeAnnotateNameTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()
        cls.tokenizer = create_tokenizer("regex", cls.cnf)
        cls.example_name = "some long name"
        cls.tokens = list(cls.tokenizer(cls.example_name)[:])
        cls.mock_cdb = unittest.mock.Mock()
        cls.mock_cdb.name2info = defaultdict(lambda: defaultdict(lambda: "P"))

    def setUp(self):
        self.mock_doc = unittest.mock.Mock()
        # self.mock_doc.ner_ents = unittest.mock.Mock()
        self.mock_doc._tokens = self.tokens
        self.mock_doc.ner_ents.append = unittest.mock.Mock()
        self.mock_doc.ner_ents.__len__ = unittest.mock.Mock(return_value=0)

    def test_old_API_has_side_effects(self):
        vocab_based_annotator.maybe_annotate_name(
            self.tokenizer, self.example_name,
            tkns=self.tokens, doc=self.mock_doc, cdb=self.mock_cdb,
            config=self.cnf)
        self.mock_doc.ner_ents.append.assert_called_once()

    def test_new_API_has_no_side_effects(self):
        vocab_based_annotator.maybe_annotate_name(
            self.tokenizer, self.example_name,
            tkns=self.tokens, doc=self.mock_doc, cdb=self.mock_cdb,
            config=self.cnf, cur_id=1)
        self.mock_doc.ner_ents.append.assert_not_called()
