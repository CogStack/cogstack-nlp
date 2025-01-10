from typing import Any

import logging
from medcat2.tokenizing.tokens import MutableDocument
from medcat2.components.types import CoreComponentType, AbstractCoreComponent
from medcat2.components.ner.vocab_based_annotator import maybe_annotate_name
from medcat2.tokenizing.tokenizers import BaseTokenizer
from medcat2.vocab import Vocab
from medcat2.cdb import CDB


logger = logging.getLogger(__name__)


class NER(AbstractCoreComponent):
    name = 'cat_ner'

    def __init__(self, tokenizer: BaseTokenizer,
                 cdb: CDB) -> None:
        self.tokenizer = tokenizer
        self.cdb = cdb
        self.config = self.cdb.config

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
        max_skip_tokens = self.config.components.ner.max_skip_tokens
        _sep = self.config.general.separator
        # Just take the tokens we need
        _doc = [tkn for tkn in doc if not tkn.to_skip]
        for i, tkn in enumerate(_doc):
            tkn = _doc[i]
            tkns = [tkn]
            # name_versions = [tkn.lower_, tkn._.norm]
            # name_versions = [tkn.norm, tkn.base.lower]
            name_versions = tkn.base.text_versions
            name = ""

            for name_version in name_versions:
                if self.cdb.has_subname(name_version):
                    if name:
                        name = name + _sep + name_version
                    else:
                        name = name_version
                    break
            if name in self.cdb.name2info and not tkn.base.is_stop:
                maybe_annotate_name(self.tokenizer, name, tkns, doc,
                                    self.cdb, self.config)
            if not name:
                # There has to be at least something appended to the name
                # to go forward
                continue
            for j in range(i+1, len(_doc)):
                if (_doc[j].base.index - _doc[j-1].base.index - 1
                        > max_skip_tokens):
                    # Do not allow to skip more than limit
                    break
                tkn = _doc[j]
                tkns.append(tkn)
                # name_versions = [tkn.norm, tkn.base.lower]
                name_versions = tkn.base.text_versions

                name_changed = False
                name_reverse = None
                for name_version in name_versions:
                    _name = name + _sep + name_version
                    if self.cdb.has_subname(_name):
                        # Append the name and break
                        name = _name
                        name_changed = True
                        break

                    if self.config.components.ner.try_reverse_word_order:
                        _name_reverse = name_version + _sep + name
                        if self.cdb.has_subname(_name_reverse):
                            # Append the name and break
                            name_reverse = _name_reverse

                if name_changed:
                    if name in self.cdb.name2info:
                        maybe_annotate_name(self.tokenizer, name, tkns, doc,
                                            self.cdb, self.config)
                elif name_reverse is not None:
                    if name_reverse in self.cdb.name2info:
                        maybe_annotate_name(self.tokenizer, name_reverse, tkns,
                                            doc, self.cdb, self.config)
                else:
                    break

        return doc

    @classmethod
    def get_init_args(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab
                      ) -> list[Any]:
        return [tokenizer, cdb]

    @classmethod
    def get_init_kwargs(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab
                        ) -> dict[str, Any]:
        return {}
