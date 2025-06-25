from typing import Optional, Union, Any, Iterator, cast
import random
import logging
from itertools import chain
from collections.abc import MutableMapping, KeysView
from contextlib import contextmanager

from medcat.cdb.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import Config, SerialisableBaseModel, ComponentConfig
from medcat.utils.defaults import StatusTypes as ST
from medcat.utils.matutils import sigmoid
from medcat.utils.config_utils import temp_changed_config
from medcat.cdb.concepts import CUIInfo, TypeInfo, get_new_cui_info
from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableEntity, MutableDocument
from medcat.components.linking.context_based_linker import (
    Linker as NormalLinker, PerDocumentTokenCache)
from medcat.components.linking.vector_context_model import ContextModel


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


TYPE_ID_PREFIX: str = "TYPE_ID:"


def add_tuis_to_cui_info(cui2info: dict[str, CUIInfo],
                         type_ids: dict[str, TypeInfo]
                         ):
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
        self._init_cnf()
        self._linker = NormalLinker(cdb, vocab, config)
        self._linker.context_model._disamb_preprocessors.append(
            self._preprocess_disamb)
        add_tuis_to_cui_info(self.cdb.cui2info, self.cdb.type_id2info)
        self._tui_context_model = ContextModel(
            self.cdb.cui2info,
            self.cdb.name2info,
            self.cdb.weighted_average_function,
            self.vocab,
            self.config.components.linking,
            self.config.general.separator)

    def _init_cnf(self):
        if not isinstance(self.config.components.linking.additional,
                          TwoStepLinkerConfig):
            logger.info("Setting default TwoStepLinkerConfig instead of %s",
                        self.config.components.linking.additional)
            self.config.components.linking.additional = TwoStepLinkerConfig()

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

        with changed_learning_rate(self.config, self.two_step_config):
            self._do_training(doc, entity, name, cuis,
                              per_cui_tuis, tuis, per_doc_valid_token_cache)

    def _do_training(self,
                     doc: MutableDocument,
                     entity: MutableEntity,
                     name: str,
                     cuis: list[str],
                     per_cui_tuis: dict[str, list[str]],
                     tuis: list[str],
                     per_doc_valid_token_cache: PerDocumentTokenCache):
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
        for entity in doc.ner_ents:
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
            per_doc_valid_token_cache: PerDocumentTokenCache,
            per_entity_weights: 'PerEntityWeights',
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
        per_cui_type_sims = {
            cui: sim
            for tui, sim in zip(suitable_tuis, tui_similarities)
            if tui is not None
            for cui in per_tui_candidates[tui.removeprefix(TYPE_ID_PREFIX)]
        }
        per_entity_weights[entity] = per_cui_type_sims
        logger.debug("Adding per CUI to %s (tokens %d..%d) weights %s",
                     cui, entity.base.start_index, entity.base.end_index,
                     per_cui_type_sims)

    def _weigh_on_inference(self, doc: MutableDocument) -> 'PerEntityWeights':
        per_entity_weights = PerEntityWeights(doc)
        per_doc_valid_token_cache = PerDocumentTokenCache()
        for entity in doc.ner_ents:
            logger.debug("Narrowing down candidates for: '%s' from %s",
                         entity.base.text, entity.link_candidates)
            self._reweigh_candidates(
                doc, entity, per_doc_valid_token_cache, per_entity_weights)
        return per_entity_weights

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        per_ent_weights: Optional[PerEntityWeights] = None
        if self.config.components.linking.train:
            self._train_for_tuis(doc)
        else:
            per_ent_weights = self._weigh_on_inference(doc)
        with temp_attribute(self, '_per_ent_weights', per_ent_weights):
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
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]
            ) -> 'TwoStepLinker':
        return cls(cdb, vocab, cdb.config)

    @property
    def two_step_config(self) -> 'TwoStepLinkerConfig':
        cnf_2step = self.config.components.linking.additional
        if not isinstance(cnf_2step, TwoStepLinkerConfig):
            raise ValueError(
                "Need to set 'config.components.linking.additional' to "
                "an instance of TwoStepLinkerConfig")
        return cnf_2step

    _DEBUG_CNT = 0  # TODO: remove

    def _preprocess_disamb(self, ent: MutableEntity, name: str,
                           cuis: list[str], similarities: list[float]) -> None:
        if cuis and all(cui.startswith(TYPE_ID_PREFIX) for cui in cuis):
            return
        if not hasattr(self, '_per_ent_weights'):
            raise ValueError("No per entity weights")
        pew = self._per_ent_weights
        if ent not in pew:
            # ignore for stuff not in here
            return
        per_cui_type_sims = pew[ent]
        cnf_2step = self.two_step_config
        for cui, type_sim in per_cui_type_sims.items():
            if cui not in cuis:
                continue
            cui_index = cuis.index(cui)
            cui_sim = similarities[cui_index]
            ts_coef = sigmoid(
                cnf_2step.alpha_sharpness * (
                    type_sim - cnf_2step.alpha_midpoint))
            logger.debug(
                "Mixing type similarity of %.4f and CUI similarity of %.4f "
                "with %.4f weight for CUI similarity",
                cui_sim, type_sim, ts_coef)
            new_sim = (1 - ts_coef) * cui_sim + ts_coef * type_sim
            similarities[cui_index] = new_sim
            logger.debug("[Per CUI weights] CUI: %s, Name: %s, "
                         "Old sim: %.3f, New sim: %.3f",
                         cui, name, cui_sim, new_sim)


class PerEntityWeights(MutableMapping[MutableEntity, dict[str, float]]):

    def __init__(self, doc: MutableDocument):
        self._doc = doc
        self._cui_weights: dict[tuple[int, int], dict[str, float]] = {}

    def _to_key(self, ent: MutableEntity) -> tuple[int, int]:
        return ent.base.start_index, ent.base.end_index

    def _from_key(self, key: tuple[int, int]) -> MutableEntity:
        start, end = key
        for ent in self._doc.ner_ents:
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


def changed_learning_rate(config: Config, two_step_cnf: 'TwoStepLinkerConfig'):
    coef = two_step_cnf.type_learning_rate_coefficient
    comp_optim = config.components.linking.optim.copy()
    for learning_rate_name in comp_optim:
        if 'lr' not in learning_rate_name:
            continue
        comp_optim[learning_rate_name] *= coef
    logger.debug("Changing learning rate from %s to %s",
                 config.components.linking.optim,
                 comp_optim)
    return temp_changed_config(
        config.components.linking, 'optim', comp_optim)


class TwoStepLinkerConfig(SerialisableBaseModel):
    alpha_midpoint: float = 0.5
    """The midpoint for the sigmoid.
    alpha = sigmoid(alpha_sharpness(similarity - alpha_midpoint))
    This is used for weighting the type similarity vs the concept similarity.
    """
    alpha_sharpness: float = 5.0
    """The sharpness for the sigmoid.
    alpha = sigmoid(alpha_sharpness(similarity - alpha_midpoint))
    This is used for weighting the type similarity vs the concept similarity.
    """
    type_learning_rate_coefficient: float = 0.2
    """The coefficient for the type-based context model learning rate.

    The idea is that since there's a far fewer classes for types,
    we need to lower the learning rate. In the Snomed examples we have
    around 10 000 more CUIs then types so a coefficient like 0.2 should be
    appropriate.
    """


@contextmanager
def temp_attribute(obj: Any, attr_name: str, attr_val: Any):
    if hasattr(obj, attr_name):
        prev_val = getattr(obj, attr_name)
        logger.warning(
            "Object '%s' already had an attribute '%s' - has type '%s'",
            obj, attr_val, type(prev_val))
    else:
        prev_val = None
    setattr(obj, attr_name, attr_val)
    yield
    # and reset
    if prev_val is not None:
        setattr(obj, attr_name, prev_val)
    else:
        delattr(obj, attr_name)
