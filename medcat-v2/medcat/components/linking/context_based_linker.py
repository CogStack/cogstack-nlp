import random
import logging
from typing import Iterator, Optional, Union

from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.tokenizing.tokens import MutableEntity, MutableDocument
from medcat.components.linking.vector_context_model import (
    ContextModel, PerDocumentTokenCache)
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import Config, ComponentConfig
from medcat.utils.defaults import StatusTypes as ST
from medcat.utils.postprocessing import create_main_ann
from medcat.tokenizing.tokenizers import BaseTokenizer


logger = logging.getLogger(__name__)


# class Linker(PipeRunner):
class Linker(AbstractCoreComponent):
    """Link to a biomedical database.

    Args:
        cdb (CDB): The Context Database.
        vocab (Vocab): The vocabulary.
        config (Config): The config.
    """

    # Custom pipeline component name
    name = 'medcat2_linker'

    # Override
    def __init__(self, cdb: CDB, vocab: Vocab, config: Config) -> None:
        self.cdb = cdb
        self.vocab = vocab
        self.config = config
        self.context_model = ContextModel(self.cdb.cui2info,
                                          self.cdb.name2info,
                                          self.cdb.weighted_average_function,
                                          self.vocab,
                                          self.config.components.linking,
                                          self.config.general.separator)
        # Counter for how often did a pair (name,cui) appear and
        # was used during training
        self.train_counter: dict = {}

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking

    def _train(self, cui: str, entity: MutableEntity, doc: MutableDocument,
               per_doc_valid_token_cache: PerDocumentTokenCache,
               add_negative: bool = True) -> None:
        name = "{} - {}".format(entity.detected_name, cui)
        # TODO - bring back subsample after?
        # Always train
        self.context_model.train(
            cui, entity, doc, per_doc_valid_token_cache, negative=False)
        if (add_negative and
                self.config.components.linking.negative_probability
                >= random.random()):
            self.context_model.train_using_negative_sampling(cui)
        self.train_counter[name] = self.train_counter.get(name, 0) + 1

    def _process_entity_train(self, doc: MutableDocument,
                              entity: MutableEntity,
                              per_doc_valid_token_cache: PerDocumentTokenCache,
                              ) -> Iterator[MutableEntity]:
        cnf_l = self.config.components.linking
        # Check does it have a detected name
        if entity.detected_name is None:
            return
        name = entity.detected_name
        cuis = entity.link_candidates

        if len(name) < cnf_l.disamb_length_limit:
            return
        if len(cuis) == 1:
            # N - means name must be disambiguated, is not the preferred
            # name of the concept, links to other concepts also.
            name_info = self.cdb.name2info.get(name, None)
            if not name_info:
                return
            if name_info['per_cui_status'][cuis[0]] == ST.MUST_DISAMBIGATE:
                return
            self._train(cui=cuis[0], entity=entity, doc=doc,
                        per_doc_valid_token_cache=per_doc_valid_token_cache)
            entity.cui = cuis[0]
            entity.context_similarity = 1
            yield entity
        else:
            for cui in cuis:
                name_info = self.cdb.name2info.get(name, None)
                if not name_info:
                    continue
                if name_info['per_cui_status'][cui] not in ST.PRIMARY_STATUS:
                    continue
                # if self.cdb.name2cuis2status[name][cui] in {'P', 'PD'}:
                self._train(
                    cui=cui, entity=entity, doc=doc,
                    per_doc_valid_token_cache=per_doc_valid_token_cache)
                # It should not be possible that one name is 'P' for
                # two CUIs, but it can happen - and we do not care.
                entity.cui = cui
                entity.context_similarity = 1
                yield entity

    def _train_on_doc(self, doc: MutableDocument) -> Iterator[MutableEntity]:
        # Run training
        for entity in doc.ner_ents:
            yield from self._process_entity_train(
                doc, entity, PerDocumentTokenCache())

    def _process_entity_nt_w_name(
            self, doc: MutableDocument,
            entity: MutableEntity,
            cuis: list[str], name: str,
            per_doc_valid_token_cache: PerDocumentTokenCache
            ) -> tuple[Optional[str], float]:
        cnf_l = self.config.components.linking
        # NOTE: there used to be the condition
        # but if there are cuis, and it's an entity - surely, there's a match?
        # And there wasn't really an alternative anyway (which could have
        # caused and exception to be raised or cui/similarity from previous
        # entity to be used)
        # if len(cuis) > 0:
        do_disambiguate = False
        name_info = self.cdb.name2info[name]
        if len(name) < cnf_l.disamb_length_limit:
            do_disambiguate = True
        elif (len(cuis) == 1 and
                name_info['per_cui_status'][cuis[0]] in ST.DO_DISAMBUGATION):
            do_disambiguate = True
        elif len(cuis) > 1:
            do_disambiguate = True

        if do_disambiguate:
            cui, context_similarity = self.context_model.disambiguate(
                cuis, entity, name, doc, per_doc_valid_token_cache)
        else:
            cui = cuis[0]
            if self.config.components.linking.always_calculate_similarity:
                context_similarity = self.context_model.similarity(
                    cui, entity, doc, per_doc_valid_token_cache)
            else:
                context_similarity = 1  # Direct link, no care for similarity
        return cui, context_similarity

    def _check_similarity(self, cui: str, context_similarity: float) -> bool:
        th_type = self.config.components.linking.similarity_threshold_type
        threshold = self.config.components.linking.similarity_threshold
        if th_type == 'static':
            return context_similarity >= threshold
        if th_type == 'dynamic':
            conf = self.cdb.cui2info[cui]['average_confidence']
            return context_similarity >= conf * threshold
        return False

    def _process_entity_inference(
            self, doc: MutableDocument,
            entity: MutableEntity,
            per_doc_valid_token_cache: PerDocumentTokenCache
            ) -> Iterator[MutableEntity]:
        # Check does it have a detected concepts
        cuis = entity.link_candidates
        if not cuis:
            return
        # Check does it have a detected name
        name = entity.detected_name
        if name is not None:
            cui, context_similarity = self._process_entity_nt_w_name(
                doc, entity, cuis, name, per_doc_valid_token_cache)
        else:
            # No name detected, just disambiguate
            cui, context_similarity = self.context_model.disambiguate(
                cuis, entity, 'unk-unk', doc, per_doc_valid_token_cache)
        logger.debug("Considering CUI %s with sim %f",
                     cui, context_similarity)

        # Add the annotation if it exists and if above threshold and in filters
        cnf_l = self.config.components.linking
        if not cui or not cnf_l.filters.check_filters(cui):
            return
        if self._check_similarity(cui, context_similarity):
            entity.cui = cui
            entity.context_similarity = context_similarity
            yield entity

    def _inference(self, doc: MutableDocument) -> Iterator[MutableEntity]:
        per_doc_valid_token_cache = PerDocumentTokenCache()
        for entity in doc.ner_ents:
            logger.debug("Linker started with entity: %s", entity.base.text)
            yield from self._process_entity_inference(
                doc, entity, per_doc_valid_token_cache)

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        # Reset main entities, will be recreated later
        doc.linked_ents.clear()
        cnf_l = self.config.components.linking

        if cnf_l.train:
            linked_entities = self._train_on_doc(doc)
        else:
            linked_entities = self._inference(doc)
        # evaluating generator here because the `all_ents` list gets
        # cleared afterwards otherwise
        le = list(linked_entities)

        doc.ner_ents.clear()
        doc.ner_ents.extend(le)
        create_main_ann(doc)

        # TODO - reintroduce pretty labels? and apply here?

        # TODO - reintroduce groups? and map here?

        return doc

    def train(self, cui: str,
              entity: MutableEntity,
              doc: MutableDocument,
              negative: bool = False,
              names: Union[list[str], dict] = [],
              per_doc_valid_token_cache: Optional[PerDocumentTokenCache] = None
              ) -> None:
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
            per_doc_valid_token_cache (PerDocumentTokenCache):
                Optionally, provide the per doc valid token cache.
        """
        if per_doc_valid_token_cache is None:
            per_doc_valid_token_cache = PerDocumentTokenCache()
        self.context_model.train(
            cui, entity, doc, per_doc_valid_token_cache, negative, names)

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]
            ) -> 'Linker':
        return cls(cdb, vocab, cdb.config)
