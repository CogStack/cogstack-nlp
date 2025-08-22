from typing import Optional

import logging
from medcat.tokenizing.tokens import MutableDocument
from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.components.ner.vocab_based_annotator import maybe_annotate_name
from medcat.utils.import_utils import ensure_optional_extras_installed
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.vocab import Vocab
from medcat.cdb import CDB
from medcat.config.config import ComponentConfig
import medcat


# NOTE: the _ is converted to - automatically
_EXTRA_NAME = "dict-ner"

# NOTE: need to do this before below import for more useful error
ensure_optional_extras_installed(medcat.__name__, _EXTRA_NAME)

from ahocorasick import Automaton # noqa


logger = logging.getLogger(__name__)


class NER(AbstractCoreComponent):
    name = 'cat_dict_ner'

    def __init__(self, tokenizer: BaseTokenizer,
                 cdb: CDB) -> None:
        self.tokenizer = tokenizer
        self.cdb = cdb
        self.config = self.cdb.config
        self.automaton = Automaton()
        self._rebuild_automaton()

    def _rebuild_automaton(self):
        # NOTE: every time the CDB changes (is dirtied)
        #       this will be recalculated
        logger.info("Rebuilding NER automaton (Aho-Corasick)")
        self.automaton.clear()
        # NOTE: we do not need name info for NER - only for linking
        ignored_min_len = 0
        for name in self.cdb.name2info.keys():
            clean_name = name.replace(self.config.general.separator, " ")
            if clean_name in self.automaton:
                # no need to duplicate
                continue
            if len(clean_name) < self.config.components.ner.min_name_len:
                # ignore names that are too short
                ignored_min_len += 1
                continue
            self.automaton.add_word(clean_name, clean_name)
        logger.debug("Ignored %d due to being smaller than minimum "
                     "allowed length (%d)", ignored_min_len,
                     self.config.components.ner.min_name_len)
        self.automaton.make_automaton()

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.ner

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        """Detect candidates for concepts - linker will then be able
        to do the rest. It adds `entities` to the doc.entities and each
        entity can have the entity.link_candidates - that the linker
        will resolve.

        Args:
            doc (MutableDocument):
                Spacy document to be annotated with named entities.

        Returns:
            doc (MutableDocument):
                Spacy document with detected entities.
        """
        if self.cdb.has_changed_names:
            self.cdb._reset_subnames()
            self._rebuild_automaton()
        text = doc.base.text.lower()
        for end_idx, raw_name in self.automaton.iter(text):
            start_idx = end_idx - len(raw_name) + 1
            cur_tokens = doc.get_tokens(start_idx, end_idx)
            if not isinstance(cur_tokens, list):
                # NOTE: this shouldn't really happen since
                #       there should be no entities defined
                #       before the NER step.
                #       But we will (at least for now) still handler this
                cur_tokens = list(cur_tokens)
            if not cur_tokens:
                # NOTE: the most likely reason for this is when matching
                #       a substring (e.g an abreviation in a longer word).
                #       In that case, no spacy tokens will match. But we
                #       don't really want to catch `mi` (for myocardial
                #       infarction) in "family".
                continue
            preprocessed_name = raw_name.replace(
                ' ', self.config.general.separator)
            maybe_annotate_name(self.tokenizer, preprocessed_name, cur_tokens,
                                doc, self.cdb, self.config)
        return doc

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]) -> 'NER':
        return cls(tokenizer, cdb)
