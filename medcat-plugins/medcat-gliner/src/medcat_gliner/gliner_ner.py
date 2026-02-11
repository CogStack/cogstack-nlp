from typing import Iterator
import logging

from gliner import GLiNER

from medcat.components.types import AbstractEntityProvidingComponent
from medcat.components.types import CoreComponentType
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import ComponentConfig, SerialisableBaseModel
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.tokenizing.tokens import MutableToken
from medcat.components.ner.vocab_based_annotator import maybe_annotate_name


logger = logging.getLogger(__name__)


class GliNERConfig(SerialisableBaseModel):
    model_name: str = "urchade/gliner_base"
    """The model to use.

    See options:
    https://huggingface.co/models?library=gliner&sort=trending
    """
    threshold: float = 0.5
    """The threshold for the prediciton.

    Higher will probably mean more false positives, while lower will
    probably mean missing some true positives (i.e more false negatives)
    """
    chunking_overlap_tokens: int = 10
    """If we're chunking the text for the HF model, what is the overlap we use.

    For text longer than 384 words (which GLiNer people say is equivalent
    to 512 tokens) the text needs to chunked in order to be processed by
    the HF model. However, if the chunking has no overalp, some of the context
    will be lost and performance will probably deteriate.
    At the same time, larger overlaps will need more data will be processed
    which leads to lower throughput.
    """


# NOTE: They allow up to 384 WORDs. They say
#       that's equivalent 512 tokens, see:
# https://github.com/urchade/GLiNER/issues/183#issuecomment-2330882600
#       However, it's easier for us to just count the tokens.
#       Also, they say you can increase it at the expense of performance
#       so I'd rather do the splitting manually at that point.
#       I tried 500 tokens, and it was consistently too many
#       so went down to 400
MAX_TOKENS_2_GLINER_AT_ONCE = 400


class GlinerNER(AbstractEntityProvidingComponent):
    name = 'gliner_ner'

    def __init__(self, tokenizer: BaseTokenizer,
                 cdb: CDB) -> None:
        super().__init__()
        self.tokenizer = tokenizer
        self.cdb = cdb
        self.config = self.cdb.config
        self._validate_cnf()
        self._init_model()

    def _validate_cnf(self):
        cnf = self.config.components.ner.custom_cnf
        if not isinstance(cnf, GliNERConfig):
            logger.warning("No GliNERConfig was set - using default")
            cnf = self.config.components.ner.custom_cnf = GliNERConfig()
        self.gliner_cnf = cnf

    def _init_model(self):
        logger.info("Init model for %s", self.gliner_cnf.model_name)
        self.model = GLiNER.from_pretrained(self.gliner_cnf.model_name)
        # init labels from type id
        self.labels = [
            tid.name for tid in
            self.cdb.type_id2info.values()]
        logger.info("Using labels: %s", self.labels)

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
                Document to be annotated with named entities.
            ents (list[MutableEntity] | None):
                The entities given. This should be None.

        Returns:
            list[MutableEntity]:
                The NER'ed entities.
        """
        if ents is not None:
            ValueError(f"Unexpected entities sent to NER: {ents}")
        if self.cdb.has_changed_names:
            self.cdb._reset_subnames()
            self._init_model()
        text = doc.base.text.lower()
        all_tkns = list(doc)
        if len(all_tkns) > MAX_TOKENS_2_GLINER_AT_ONCE:
            return self._split_and_predict(doc, text, all_tkns)
        return self._predict(doc, text, 0)

    def _create_splits(self, all_tkns: list[MutableToken],
                       full_text: str) -> Iterator[tuple[str, int]]:
        overlap_tkns = self.gliner_cnf.chunking_overlap_tokens
        leftover_tokens = list(all_tkns)
        while leftover_tokens:
            cur_tokens = leftover_tokens[:MAX_TOKENS_2_GLINER_AT_ONCE]
            # keep overlap number of tokens
            leftover_tokens = leftover_tokens[
                MAX_TOKENS_2_GLINER_AT_ONCE - overlap_tkns:]
            start_char = cur_tokens[0].base.char_index
            end_char = cur_tokens[-1].base.char_index + len(
                cur_tokens[-1].base.text)
            cur_text = full_text[start_char:end_char]
            yield cur_text, start_char

    def _split_and_predict(self, doc: MutableDocument,
                           full_text: str,
                           all_tkns: list[MutableToken]
                           ) -> list[MutableEntity]:
        all_out: list[MutableEntity] = []
        for cur_text, offset in self._create_splits(all_tkns, full_text):
            all_out.extend(self._predict(doc, cur_text, offset))
        return all_out

    def _predict(self, doc: MutableDocument, text: str,
                 char_offset: int) -> list[MutableEntity]:
        ner_ents: list[MutableEntity] = []
        for ent_dict in self.model.predict_entities(
                text, self.labels, self.gliner_cnf.threshold):
            start_char = ent_dict["start"] + char_offset
            end_char = ent_dict["end"] + char_offset
            # TODO: check the "text"?
            # value = ent_dict["text"]
            tokens = doc.get_tokens(start_char, end_char-1)
            tokens_str = [tkn.base.lower for tkn in tokens]
            preprocessed_name = self.config.general.separator.join(tokens_str)
            if preprocessed_name not in self.cdb.name2info:
                continue
            ent = maybe_annotate_name(
                self.tokenizer, preprocessed_name, tokens,
                doc, self.cdb, self.config, len(ner_ents))
            if ent:
                ner_ents.append(ent)
        return ner_ents

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: str | None
            ) -> 'GlinerNER':
        return cls(tokenizer, cdb)
