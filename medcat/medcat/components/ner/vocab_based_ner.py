from typing import Optional
from itertools import product
from collections.abc import Iterator

import logging
from medcat.tokenizing.tokens import MutableDocument, MutableEntity, MutableToken
from medcat.components.types import CoreComponentType
from medcat.components.types import AbstractEntityProvidingComponent
from medcat.components.ner.vocab_based_annotator import maybe_annotate_name
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.vocab import Vocab
from medcat.cdb import CDB
from medcat.config.config import ComponentConfig


logger = logging.getLogger(__name__)


class NER(AbstractEntityProvidingComponent):
    name = 'cat_ner'

    def __init__(self, tokenizer: BaseTokenizer,
                 cdb: CDB) -> None:
        super().__init__()
        self.tokenizer = tokenizer
        self.cdb = cdb
        self.config = self.cdb.config

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.ner

    def predict_entities(self, doc: MutableDocument,
                         ents: list[MutableEntity] | None = None
                         ) -> list[MutableEntity]:
        """Detect candidates for concepts - linker will then be able
        to do the rest. It adds `entities` to the doc.entities and each
        entity can have the entity.link_candidates - that the linker
        will resolve.

        Args:
            doc (MutableDocument):
                Spacy document to be annotated with named entities.
            ents (list[MutableEntity] | None):
                The entities given. This should be None.

        Returns:
            list[MutableEntity]:
                The NER'ed entities.
        """
        max_skip_tokens = self.config.components.ner.max_skip_tokens
        _sep = self.config.general.separator
        # Just take the tokens we need
        _doc = [tkn for tkn in doc if not tkn.to_skip]
        ner_ents: list[MutableEntity] = []
        for i, tkn in enumerate(_doc):
            tkn = _doc[i]
            tkns = [tkn]
            # name_versions = [tkn.lower_, tkn._.norm]
            # name_versions = [tkn.norm, tkn.base.lower]
            start_tkn_name = ""

            for name_version in tokens_to_raw_name_opts(
                tkns, _sep,
                self.config.components.ner.try_reverse_word_order
            ):
                if self.cdb.has_subname(name_version):
                    start_tkn_name = name_version
                    break
            # if name is in CDB
            if start_tkn_name in self.cdb.name2info and not tkn.base.is_stop:
                ent = maybe_annotate_name(
                    self.tokenizer, start_tkn_name, tkns, doc,
                    self.cdb, self.config, len(ner_ents))
                if ent:
                    ner_ents.append(ent)
            # if name is not a subname CDB (explicitly)
            if not start_tkn_name:
                # There has to be at least something appended to the name
                # to go forward
                continue
            # if name is a part of a concept
            # we start adding onto it to get a match
            cur_full_name = start_tkn_name
            for j in range(i + 1, len(_doc)):
                if (_doc[j].base.index - _doc[j - 1].base.index - 1
                        > max_skip_tokens):
                    # Do not allow to skip more than limit
                    break
                tkn = _doc[j]
                tkns.append(tkn)

                name_changed = False
                for name_version in tokens_to_raw_name_opts(
                    tkns, _sep,
                    self.config.components.ner.try_reverse_word_order
                ):
                    if self.cdb.has_subname(name_version):
                        # Append the name and break
                        cur_full_name = name_version
                        name_changed = True
                        break

                if name_changed:
                    if cur_full_name in self.cdb.name2info:
                        ent = maybe_annotate_name(
                            self.tokenizer, cur_full_name, tkns, doc,
                            self.cdb, self.config, len(ner_ents))
                        if ent:
                            ner_ents.append(ent)
                else:
                    break
        return ner_ents

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]) -> 'NER':
        return cls(tokenizer, cdb)


def tokens_to_raw_name_opts(
    tkns: list[MutableToken],
    separator: str,
    try_reverse_word_order: bool,
    prefix: str = "",
) -> Iterator[str]:
    per_tkn_opts: list[list[str]] = []
    if prefix:
        per_tkn_opts.append([prefix])
    for tkn in tkns:
        name_versions = tkn.base.text_versions
        # NOTE: I want to preserve order since the text versions returns in
        #       the correct / expected order in which to check
        unique_versions = []
        # NOTE: we want to avoid duplicate names so we only keep uinque ones
        #       otherwise the option set can become massive
        for version in name_versions:
            # NOTE: we're checking contents of a list, not ideal
            #       but we should only ever have 0 or 1 items in the list
            #       at time of check so shouldn't be too bad
            if version not in unique_versions:
                unique_versions.append(version)
        per_tkn_opts.append(unique_versions)

    out_list = list(product(*per_tkn_opts))
    if try_reverse_word_order:
        out_list.extend(list(product(*per_tkn_opts[::-1])))
    return map(separator.join, out_list)
