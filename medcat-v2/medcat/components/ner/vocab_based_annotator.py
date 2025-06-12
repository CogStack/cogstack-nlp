"""I would just ignore this whole class, it's just a lot of rules that work
nicely for CDB once the software is trained the main thing are the context
vectors.
"""
import logging
from typing import Optional
from medcat.tokenizing.tokens import (MutableEntity, MutableToken,
                                      MutableDocument)
from medcat.cdb import CDB
from medcat.config import Config
from medcat.tokenizing.tokenizers import BaseTokenizer

logger = logging.getLogger(__name__)


def annotate_name(tokenizer: BaseTokenizer, name: str,
                  tkns: list[MutableToken],
                  doc: MutableDocument, cdb: CDB,
                  label: str):
    entity: MutableEntity = tokenizer.create_entity(
        doc, tkns[0].base.index, tkns[-1].base.index + 1, label=label)
    # Only set this property when using a vocab approach
    # and where this name fits a name in the cdb.
    # All standard name entity recognition models will not set this.
    entity.detected_name = name
    entity.link_candidates = list(cdb.name2info[name]['per_cui_status'])
    entity.id = len(doc.ner_ents)
    entity.confidence = -1  # This does not calculate confidence
    # Append the entity to the document
    doc.ner_ents.append(entity)

    # Not necessary, but why not
    logger.debug("NER detected an entity.\n\tDetected name: %s" +
                 "\n\tLink candidates: %s\n", entity.detected_name,
                 entity.link_candidates)
    return entity


def maybe_annotate_name(tokenizer: BaseTokenizer, name: str,
                        tkns: list[MutableToken],
                        doc: MutableDocument, cdb: CDB, config: Config,
                        label: str = 'concept'
                        ) -> Optional[MutableEntity]:
    """Given a name it will check should it be annotated based on config rules.
    If yes the annotation will be added to the doc.entities array.

    Args:
        tokenizer (BaseTokenizer):
            The tokenizer (probably SpaCy).
        name (str):
            The name found in the text of the document.
        tkns (list[MutableToken]):
            Tokens that belong to this name in the spacy document.
        doc (BaseDocument):
            Spacy document to be annotated with named entities.
        cdb (CDB):
            Concept database.
        config (Config):
            Global config for medcat.
        label (str):
            Label for this name (usually `concept` if we are using
            a vocab based approach).

    Returns:
        Optional[BaseEntity]: The entity, if relevant.
    """

    logger.debug("Maybe annotating name: %s", name)

    # Check uppercase to distinguish uppercase and lowercase
    # words that have a different meaning.
    if config.components.ner.check_upper_case_names:
        # Check whether name is completely uppercase in CDB.
        is_upper = (cdb.name2info[name]['is_upper']
                    if name in cdb.name2info else False)
        if is_upper:
            # Check whether tokens are also in uppercase. If tokens
            # are not in uppercase, there is a mismatch.
            if not all([x.base.is_upper for x in tkns]):
                return None

    if len(name) >= config.components.ner.min_name_len:
        # Check the upper case limit, last part checks if it is
        # one token and uppercase
        if (len(name) >= config.components.ner.upper_case_limit_len or
                (len(tkns) == 1 and tkns[0].base.is_upper)):
            # Everything is fine, mark name
            return annotate_name(tokenizer, name, tkns, doc, cdb, label)

    return None
