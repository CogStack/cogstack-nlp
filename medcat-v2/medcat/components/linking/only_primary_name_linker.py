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


class PrimNameLinker(Linker):
    """Linker that only links primary names (or other 1-1 matches).

    This linker avoids the hard part of linking - the disambiguation.
    This should allow it to work faster, but (generally) at the expense
    of performance.
    """
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
        cnf_l = self.config.components.linking
        if cnf_l.filter_before_disamb:
            cuis = [cui for cui in cuis if cnf_l.filters.check_filters(cui)]
        if not cuis:
            logger.debug("No CUIs that fit filter for %s", entity)
            return
        if len(cuis) == 1:
            if cnf_l.filters.check_filters(cuis[0]):
                logger.debug("Choosing only possible CUI %s for %s",
                             cuis[0], entity)
                entity.cui = cuis[0]
                entity.context_similarity = 1.0
                yield entity
            else:
                logger.debug(
                    "A single CUI (%s) was mapped to for %s but not in filter",
                    cuis[0], entity)
            return
        primary_cuis = [cui for cui in cuis
                        if (self.cdb.name2info[name]['per_cui_status'][cui]
                            in StatusTypes.PRIMARY_STATUS and
                            cnf_l.filters.check_filters(cui))]
        if not primary_cuis:
            logger.debug("No primary CUIs for name %s", name)
            return
        if len(primary_cuis) > 1:
            logger.debug(
                "Ambiguous primary CUIs for name %s: %s", name, primary_cuis)
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
