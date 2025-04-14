from typing import Optional, Union, Any, Iterator, cast
import random
import logging
from itertools import chain
from collections.abc import MutableMapping, KeysView

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
    # 70% cui, 30% type ID
    ALPHA = 0.7
    # Custom pipeline component name
    name = 'medcat2_two_step_linker'

    # Override
    def __init__(self, cdb: CDB, vocab: Vocab, config: Config) -> None:
        self.cdb = cdb
        self.vocab = vocab
        self.config = config
        self._linker = NormalLinker(cdb, vocab, config)
        add_tuis_to_cui_info(self.cdb.cui2info, self.cdb.type_id2info)
        self._tui_context_model = ContextModel(
            self.cdb.cui2info,
            self.cdb.name2info,
            self.cdb.weighted_average_function,
            self.vocab,
            self.config.components.linking,
            self.config.general.separator,
            disamb_preprocessors=[self._preprocess_disamb])

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

    def _reweigh_candidates(
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
        (suitable_tuis,
         tui_similarities, _) = self._tui_context_model.get_all_similarities(
            tuis, entity, name, doc, per_doc_valid_token_cache)
        per_cui_weight = {
            cui: sim
            for tui, sim in zip(suitable_tuis, tui_similarities)
            if tui is not None
            for cui in per_tui_candidates[tui.removeprefix(TYPE_ID_PREFIX)]
        }
        self._per_entity_weights[entity] = per_cui_weight
        logger.debug("Adding per CUI to %s (tokens %d..%d) weights %s",
                     cui, entity.base.start_index, entity.base.end_index,
                     per_cui_weight)

    def _weigh_on_inference(self, doc: MutableDocument) -> None:
        self._per_entity_weights = PerEntityWeights(doc)
        per_doc_valid_token_cache = PerDocumentTokenCache()
        for entity in doc.all_ents:
            logger.debug("Narrowing down candidates for: '%s' from %s",
                         entity.base.text, entity.link_candidates)
            self._reweigh_candidates(
                doc, entity, per_doc_valid_token_cache)
        # clean up
        self._per_entity_weights.clear()

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        if self.config.components.linking.train:
            self._train_for_tuis(doc)
        else:
            self._weigh_on_inference(doc)
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

    def _preprocess_disamb(self, ent: MutableEntity, name: str,
                           cuis: list[str], similarities: list[float]) -> None:
        if ent not in self._per_entity_weights:
            # ignore for stuff not in here
            return
        per_cui_weights = self._per_entity_weights[ent]
        ts_coef = self.ALPHA
        for cui, weight in per_cui_weights.items():
            if cui not in cuis:
                continue
            cui_index = cuis.index(cui)
            prev_sim = similarities[cui_index]
            new_sim = ts_coef * prev_sim + (1 - ts_coef) * weight
            similarities[cui_index] = new_sim
            logger.debug("[Per CUI weights] CUI: %s, Name: %s, "
                         "Old sim: %.3f, New sim: %.3f",
                         prev_sim, new_sim)


class PerEntityWeights(MutableMapping[MutableEntity, dict[str, float]]):

    def __init__(self, doc: MutableDocument):
        self._doc = doc
        self._cui_weights: dict[tuple[int, int], dict[str, float]] = {}

    def _to_key(self, ent: MutableEntity) -> tuple[int, int]:
        return ent.base.start_index, ent.base.end_index

    def _from_key(self, key: tuple[int, int]) -> MutableEntity:
        start, end = key
        for ent in self._doc.all_ents:
            if ent.base.start_index == start and ent.base.end_index == end:
                return ent
        raise ValueError("Unable to find entity corresponding to "
                         f"{start}...{end} (token indices) within doc "
                         f"{self._doc}")

    def __getitem__(self, ent: MutableEntity):
        return self._cui_weights[self._to_key(ent)]

    def __contains__(self, key: object):
        # NOTE: shouldn't ever really be anything else
        ent = cast(MutableEntity, key)
        return self._to_key(ent) in self._cui_weights

    def __setitem__(self, ent: MutableEntity, value: dict[str, float]):
        self._cui_weights[self._to_key(ent)] = value

    def __delitem__(self, key: MutableEntity) -> None:
        del self._cui_weights[self._to_key(key)]

    def __iter__(self) -> Iterator[MutableEntity]:
        return (self._from_key(k) for k in self._cui_weights)

    def __len__(self) -> int:
        return len(self._cui_weights)

    def keys(self) -> KeysView[MutableEntity]:
        return {self._from_key(k): None for k in self._cui_weights}.keys()
