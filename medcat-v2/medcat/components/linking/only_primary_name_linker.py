from typing import Iterator, Optional, Union
import logging

from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.components.linking.context_based_linker import Linker
from medcat.components.linking.vector_context_model import (
    PerDocumentTokenCache)
from medcat.utils.defaults import StatusTypes
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config import Config


logger = logging.getLogger(__name__)


class OnlyPrimaryNamesLinker(Linker):
    name = 'primary_name_only_linker'

    def __init__(self, cdb: CDB, vocab: Vocab, config: Config) -> None:
        super().__init__(cdb, vocab, config)
        # don't need / use the context model
        del self.context_model

    def _process_entity_inference(
            self, doc: MutableDocument,
            entity: MutableEntity,
            per_doc_valid_token_cache: PerDocumentTokenCache
            ) -> Iterator[MutableEntity]:
        cuis = entity.link_candidates
        if not cuis:
            return
        # Check does it have a detected name
        name = entity.detected_name
        if name is None:
            logger.info("No name detected for entity %s", entity)
            return
        primary_cuis = [cui for cui, status in
                        self.cdb.name2info[name]["per_cui_status"].items()
                        if status in StatusTypes.PRIMARY_STATUS]
        if not primary_cuis:
            logger.info("No pimary CUIs for name %s", name)
            return
        if len(primary_cuis) > 1:
            logger.info(
                "Ambiguous pimary CUIs for name %s: %s", name, primary_cuis)
            return
        cui = primary_cuis[0]
        entity.cui = cui
        entity.context_similarity = 1.0
        yield entity

    def train(self, cui: str,
              entity: MutableEntity,
              doc: MutableDocument,
              negative: bool = False,
              names: Union[list[str], dict] = [],
              per_doc_valid_token_cache: Optional[PerDocumentTokenCache] = None
              ) -> None:
        raise NoTrainingException("Training is not supported for this linker")

    def _train_on_doc(self, doc: MutableDocument,
                      ner_ents: list[MutableEntity]
                      ) -> Iterator[MutableEntity]:
        raise NoTrainingException("Training is not supported for this linker")


class NoTrainingException(ValueError):
    pass
