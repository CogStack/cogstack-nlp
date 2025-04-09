from typing import Optional, Union, Any
import random
import logging
from itertools import chain

from medcat2.cdb.cdb import CDB
from medcat2.vocab import Vocab
from medcat2.config.config import Config
from medcat2.utils.defaults import StatusTypes as ST
from medcat2.cdb.concepts import CUIInfo, TypeInfo, get_new_cui_info
from medcat2.components.types import CoreComponentType, AbstractCoreComponent
from medcat2.tokenizing.tokenizers import BaseTokenizer
from medcat2.tokenizing.tokens import MutableEntity, MutableDocument
from medcat2.components.linking.context_based_linker import (
    Linker as NormalLinker, PerDocumentTokenCache)
from medcat2.components.linking.vector_context_model import ContextModel


logger = logging.getLogger(__name__)


TYPE_ID_PREFIX: str = "TYPE_ID:"


def add_tuis_to_cui_info(cui2info: dict[str, CUIInfo],
                         type_ids: dict[str, TypeInfo]
                         ):  # -> dict[str, CUIInfo]:
    for tid, tid_info in type_ids.items():
        prefixed_tid = f"{TYPE_ID_PREFIX}{tid}"
        if prefixed_tid not in cui2info:
            cui2info[prefixed_tid] = get_new_cui_info(
                tid, preferred_name=tid_info.name, names={tid_info.name})


class TwoStepLinker(AbstractCoreComponent):
    """Link to a biomedical database.

    Args:
        cdb (CDB): The Context Database.
        vocab (Vocab): The vocabulary.
        config (Config): The config.
    """
    # Custom pipeline component name
    name = 'medcat2_two_step_linker'

    # Override
    def __init__(self, cdb: CDB, vocab: Vocab, config: Config) -> None:
        self.cdb = cdb
        self.vocab = vocab
        self.config = config
        self._linker = NormalLinker(cdb, vocab, config)
        add_tuis_to_cui_info(self.cdb.cui2info, self.cdb.type_id2info)
        self._tui_linker = NormalLinker(cdb, vocab, config)
        self._tui_context_model = ContextModel(
            self.cdb.cui2info,
            self.cdb.name2info,
            self.cdb.weighted_average_function,
            self.vocab,
            self.config.components.linking,
            self.config.general.separator)

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking

    def _train_tuis(self, tui: str, entity: MutableEntity,
                    doc: MutableDocument,
                    per_doc_valid_token_cache: PerDocumentTokenCache,
                    add_negative: bool = True) -> None:
        self._tui_context_model.train(
            tui, entity, doc, per_doc_valid_token_cache, negative=False)
        if (add_negative and
                self.config.components.linking.negative_probability
                >= random.random()):
            self._tui_context_model.train_using_negative_sampling(tui)

    def _process_entity_train_tuis(
            self, doc: MutableDocument, entity: MutableEntity,
            per_doc_valid_token_cache: PerDocumentTokenCache) -> None:
        # Check does it have a detected name
        name = entity.detected_name
        if name is None:
            return
        cuis = entity.link_candidates
        # ignore duplicates, but create a list
        per_cui_tuis = {cui: [
            f"{TYPE_ID_PREFIX}{tui}"
            for tui in self.cdb.cui2info[cui]['type_ids']] for cui in cuis}
        tuis = list(set(chain(*per_cui_tuis.values())))

        if len(tuis) == 1:
            self._train_tuis(
                tui=tuis[0], entity=entity, doc=doc,
                per_doc_valid_token_cache=per_doc_valid_token_cache)
        else:
            # TODO: find most appropriate CUIs
            name_info = self.cdb.name2info.get(name, None)
            if name_info is None:
                return
            for cui in cuis:
                if name_info['per_cui_status'][cui] not in ST.PRIMARY_STATUS:
                    continue
                # only primary names
                for tui in per_cui_tuis[cui]:
                    self._train_tuis(
                        tui=tui, entity=entity, doc=doc,
                        per_doc_valid_token_cache=per_doc_valid_token_cache)

    def _train_for_tuis(self, doc: MutableDocument) -> None:
        # Run training
        for entity in doc.all_ents:
            self._process_entity_train_tuis(
                doc, entity, PerDocumentTokenCache())

    def _check_similarity(self, cui: str, context_similarity: float) -> bool:
        th_type = self.config.components.linking.similarity_threshold_type
        threshold = self.config.components.linking.similarity_threshold
        if th_type == 'static':
            return context_similarity >= threshold
        if th_type == 'dynamic':
            conf = self.cdb.cui2info[cui]['average_confidence']
            return context_similarity >= conf * threshold
        return False

    def _narrow_down_candidates(
            self, doc: MutableDocument,
            entity: MutableEntity,
            per_doc_valid_token_cache: PerDocumentTokenCache
            ) -> None:
        # Check does it have a detected concepts
        cuis = entity.link_candidates
        if not cuis:
            return
        per_tui_candidates: dict[str, list[str]] = {}
        for cui in cuis:
            for tid in self.cdb.cui2info[cui]['type_ids']:
                if tid not in per_tui_candidates:
                    per_tui_candidates[tid] = []
                per_tui_candidates[tid].append(cui)
        # NOTE: adding prefix to differentiate from regular CUIs
        tuis = [f"{TYPE_ID_PREFIX}{tid}" for tid in per_tui_candidates]
        # TODO: how do I only use ones that are allowed filter-wise?
        cnf_l = self.config.components.linking
        if cnf_l.filters.cuis:
            # this should check whether a TUI that's listed above corresponds
            # to any CUIs in the list of allowed ones
            # and only keep the ones that do
            num_before = len(tuis)
            allowed_tuis = set(
                f"{TYPE_ID_PREFIX}{tui4cui}" for cui in cnf_l.filters.cuis
                if cui in self.cdb.cui2info
                for tui4cui in self.cdb.cui2info[cui]['type_ids'])
            tuis = list(filter(allowed_tuis.__contains__, tuis))
            logger.debug("Filtered from %d to %d due to %d CUIs in filters",
                         num_before, len(tuis), len(cnf_l.filters.cuis))
        if cnf_l.filters.cuis_exclude:
            # this should check whether a TUI that's listed above corresponds
            # to any CUIs in the list of excluded ones
            # and only keep ones that don't
            raise ValueError(
                "TODO - filter based on EXCLUDED cuis: "
                f"{cnf_l.filters.cuis_exclude}")
        name = entity.detected_name
        if name is None:
            # ignore if there's no name found
            # in my experience, this shouldn't really happen anyway
            return
        tui, context_similarity = self._tui_context_model.disambiguate(
            tuis, entity, name, doc, per_doc_valid_token_cache)

        if tui and self._check_similarity(tui, context_similarity):
            # now resetting the link candidates to only ones allowed for TUI
            final_candidates = per_tui_candidates[tui[len(TYPE_ID_PREFIX):]]
            logger.debug("Narrowed down to TUI %s, and subsequently CUIs: %s",
                         tui, final_candidates)
            entity.link_candidates = final_candidates

    def _narrow_down_on_inference(self, doc: MutableDocument) -> None:
        per_doc_valid_token_cache = PerDocumentTokenCache()
        for entity in doc.all_ents:
            logger.debug("Narrowing down candidates for: %s", entity.base.text)
            self._narrow_down_candidates(
                doc, entity, per_doc_valid_token_cache)

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        if self.config.components.linking.train:
            self._train_for_tuis(doc)
        else:
            self._narrow_down_on_inference(doc)
        return self._linker(doc)

    def train(self, cui: str,
              entity: MutableEntity,
              doc: MutableDocument,
              negative: bool = False,
              names: Union[list[str], dict] = []) -> None:
        """Train the linker.

        This simply trains the context model.

        Args:
            cui (str): The CUI to train.
            entity (BaseEntity): The entity we're at.
            doc (BaseDocument): The document within which we're working.
            negative (bool): Whether or not the example is negative.
                Defaults to False.
            names (list[str]/dict):
                Optionally used to update the `status` of a name-cui
                pair in the CDB.
        """
        pdc = PerDocumentTokenCache()
        tuis = self.cdb.cui2info[cui]['type_ids']
        for tui in tuis:
            # one CUI may have multiple type IDs
            tui = next(iter(tuis))
            self._tui_context_model.train(f"{TYPE_ID_PREFIX}{tui}",
                                          entity, doc, pdc,
                                          negative=negative, names=names)
        self._linker.train(cui, entity, doc, negative, names,
                           per_doc_valid_token_cache=pdc)

    @classmethod
    def get_init_args(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                      model_load_path: Optional[str]) -> list[Any]:
        return [cdb, vocab, cdb.config]

    @classmethod
    def get_init_kwargs(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                        model_load_path: Optional[str]) -> dict[str, Any]:
        return {}
