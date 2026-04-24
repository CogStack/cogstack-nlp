from pathlib import Path
from typing import Any, Optional, Union
from medcat.tokenizing.tokens import MutableDocument, MutableEntity, MutableToken
from medcat.components.types import CoreComponentType, TrainableComponent
from medcat.components.types import AbstractEntityProvidingComponent
from medcat.components.ner.vocab_based_annotator import annotate_name
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.vocab import Vocab
from medcat.cdb import CDB
from medcat.config.config import ComponentConfig
from medcat.storage.serialisables import AbstractManualSerialisable
from transformers import AutoTokenizer, AutoModelForTokenClassification
from medcat_transformer_ner.config import TransformerNER
import logging
import os
import torch


import numpy as np
from collections import Counter

logger = logging.getLogger(__name__)


class NER(AbstractEntityProvidingComponent, TrainableComponent, AbstractManualSerialisable):
    name = 'transformer_ner'

    comp_name = "transformer_ner"
    _MODEL_FOLDER_NAME = "trainable_embedding_model"
    _MODEL_STATE_FILE_NAME = "model_state.pt"

    def __init__(self, tokenizer: BaseTokenizer,
                 cdb: CDB) -> None:
        super().__init__()
        self.tokenizer = tokenizer
        self.cdb = cdb
        self.config = self.cdb.config

        # NER model stuff!
        self.cnf_ner: TransformerNER = self.config.components.ner
        self.label2id = {
            "O": 0,
            "B-ENT": 1,
            "I-ENT": 2
        }
        self.id2label = {v: k for k, v in self.label2id.items()}
        self._model_init_kwargs = dict()
        self.load_transformers(self.cnf_ner.language_model_name)
        self.max_token_length = self.cnf_ner.max_token_length
        self.overlap_chunking = self.cnf_ner.overlap_chunking
        # class_weights = torch.tensor([
        #     0.2,   # O
        #     1.0,   # B-ENT
        #     1.0    # I-ENT
        # ], device=self.device)
        # self.loss_fct = torch.nn.CrossEntropyLoss(
        #     weight=class_weights,
        #     ignore_index=-100
        # )

    @staticmethod
    def _resolve_model_source(path_or_model_name: Union[str, Path]) -> str:
        """Return local absolute path if it exists, otherwise keep HF model id."""
        candidate = Path(path_or_model_name).expanduser()
        if candidate.exists():
            return str(candidate.resolve())
        return str(path_or_model_name)
    
    def _get_model_init_kwargs(self) -> dict[str, Any]:
        """Build kwargs passed to ModelForEmbeddingLinking.from_pretrained."""
        return dict(self._model_init_kwargs)

    def load_transformers(self, language_model_name: Union[str, Path]) -> None:
        """Load tokenizer/model from local path or Hugging Face model id."""
        model_source = self._resolve_model_source(language_model_name)
        model_init_kwargs = self._get_model_init_kwargs()
        
        if (
            not hasattr(self, "model")
            or not hasattr(self, "transformer_tokenizer")
            or model_source != self._loaded_model_source
            or model_init_kwargs != self._loaded_model_init_kwargs
        ):
            self.cnf_ner.language_model_name = str(language_model_name)
            
            self.transformer_tokenizer = AutoTokenizer.from_pretrained(
                model_source,
                clean_up_tokenization_spaces=False # might be an issue
            )
            self.model = AutoModelForTokenClassification.from_pretrained(
                model_source,
                num_labels=3,
                id2label=self.id2label,
                label2id=self.label2id,
            )
            self.model.eval()
            self.device = torch.device(
                self.cnf_ner.gpu_device
                or ("cuda" if torch.cuda.is_available() else "cpu")
            )
            self.model.to(self.device)
            self._loaded_model_source = model_source
            self._loaded_model_init_kwargs = model_init_kwargs
            self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=2e-5, weight_decay=0.01)
            logger.debug(
                "Loaded embedding model: %s (resolved source: %s) with kwargs=%s " \
				"on device: %s",
                language_model_name,
                model_source,
                model_init_kwargs,
                self.device,
            )

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.ner

    def _chunk_and_encode(self, 
                          text: str, 
                          entities: Optional[list[MutableEntity]] = None
                          ) -> tuple[list, list, list, list, Optional[list]]:
        labels_enabled = entities is not None
        # First pass: tokenize full text to get offsets for chunking and label alignment
        base_encoding = self.transformer_tokenizer(
            text,
            return_offsets_mapping=True,
            add_special_tokens=False
        )

        offsets = base_encoding["offset_mapping"]

        stride = self.max_token_length - int(self.max_token_length * self.overlap_chunking)

        n_tokens = len(base_encoding["input_ids"])
        start_idx = 0

        input_ids = []
        attention_masks = []
        all_labels = [] if labels_enabled else None
        offset_mappings = []
        chunk_char_starts = []
        while start_idx < n_tokens:
            end_idx = min(start_idx + self.max_token_length, n_tokens)

            chunk_offsets = offsets[start_idx:end_idx]

            char_start = chunk_offsets[0][0]
            char_end = chunk_offsets[-1][1]
            chunk_text = text[char_start:char_end]

            # Rebase entities to chunk
            # iff this is a training example
            if labels_enabled:
                chunk_entities = []
                for ent in entities:
                    ent_start = ent.base.start_char_index
                    ent_end = ent.base.end_char_index

                    if ent_end > char_start and ent_start < char_end:
                        chunk_entities.append({
                            "start": ent_start - char_start,
                            "end": ent_end - char_start
                        })

            # Tokenize chunk
            encoding = self.transformer_tokenizer(
                chunk_text,
                return_offsets_mapping=True,
                truncation=True,
                padding="max_length",
                max_length=self.max_token_length
            )

            offsets_chunk = encoding["offset_mapping"]

            # Label alignment to relevant chunks
            if labels_enabled:
                labels = [
                    -100 if (start == end) else self.label2id["O"]
                    for start, end in offsets_chunk
                ]


                for ent in chunk_entities:
                    started = False
                    for i, (token_start, token_end) in enumerate(offsets_chunk):
                        if token_start < ent["end"] and token_end > ent["start"]:
                            if not started:
                                labels[i] = self.label2id["B-ENT"]
                                started = True
                            else:
                                labels[i] = self.label2id["I-ENT"]

                all_labels.append(labels)

            input_ids.append(encoding["input_ids"])
            attention_masks.append(encoding["attention_mask"])
            offset_mappings.append(offsets_chunk)
            chunk_char_starts.append(char_start)

            if end_idx == n_tokens:
                break

            start_idx += stride
        input_ids = torch.tensor(input_ids, dtype=torch.long).to(self.device)
        attention_masks = torch.tensor(attention_masks, dtype=torch.long).to(self.device)
        if labels_enabled:
            all_labels = torch.tensor(all_labels, dtype=torch.long).to(self.device)
        return input_ids, attention_masks, offset_mappings, chunk_char_starts, all_labels

    def _focal_loss(self, logits, labels, gamma=2.0, ignore_index=-100):
        # flatten
        logits = logits.view(-1, logits.size(-1))
        labels = labels.view(-1)

        # mask ignored
        valid_mask = labels != ignore_index
        logits = logits[valid_mask]
        labels = labels[valid_mask]

        # standard CE
        ce_loss = torch.nn.functional.cross_entropy(logits, labels, reduction='none')

        # pt = probability of correct class
        pt = torch.exp(-ce_loss)

        # focal scaling
        loss = ((1 - pt) ** gamma) * ce_loss

        return loss.mean()
    
    def train(self, cui: str,
            entity: MutableEntity,
            doc: MutableDocument,
            negative: bool = False,
            names: Union[list[str], dict] = []) -> None:
        """Train the NER component on a given document. This is used in the
        supervised training loop of the MedCAT trainer.
        """
        # if this is the last entity, we'll train
        # kind of a hacky work around, but it's minimal impact on the CAT trainer
        if entity is doc.ner_ents[-1]:
            text = doc.base.text
            entities = doc.ner_ents
            input_ids, attention_masks, _, _, labels = self._chunk_and_encode(text, entities)
            self.optimizer.zero_grad()
            self.model.train()
            
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_masks,
                labels=labels
            )
            
            loss = outputs.loss
            loss.backward()

            logger.debug("NER training step - loss: ", 
                         loss.item())

            self.optimizer.step()

    def _decode_chunk(self, preds, offsets_chunk, chunk_char_start):
        """For inference only. Decode a single chunk of predictions into entity 
        spans, then merge them across chunks."""
        spans = []
        current = None

        for pred_id, (tok_start, tok_end) in zip(preds, offsets_chunk):

            # skip padding / special tokens
            if (tok_start, tok_end) == (0, 0):
                continue

            label = self.id2label[pred_id]

            # if label is "O", we close any open entity span and move on
            if label == "O":
                if current is not None:
                    spans.append(current)
                    current = None
                continue

            # This is a bit too general for a binary ENT/ Non Ent
            # But it's extendable... maybe!
            prefix, ent_type = label.split("-", 1)

            abs_start = chunk_char_start + tok_start
            abs_end = chunk_char_start + tok_end

            # if prefix is "B", we start a new entity span, closing any 
            # open one first. If prefix is "I", we continue the current 
            # span if it's the same entity type, otherwise we treat it 
            # as a new "B" span (this handles broken BIO sequences).
            if prefix == "B":
                if current is not None:
                    spans.append(current)
                current = {
                    "start": abs_start,
                    "end": abs_end,
                    "label": ent_type
                }

            # if prefix is "I", we continue the current span if it's 
            # the same entity type, otherwise we treat it as a new "B" 
            # span (this handles broken BIO sequences).
            # TODO: other methods of handling broken BIO?
            elif prefix == "I":
                if current is not None and current["label"] == ent_type:
                    current["end"] = abs_end
                else:
                    # broken BIO -> treat as B
                    current = {
                        "start": abs_start,
                        "end": abs_end,
                        "label": ent_type
                    }

        if current is not None:
            spans.append(current)

        return spans

    def _merge_spans(self, spans):
        """Merge spans across chunk boundaries. This is required before creating 
        entities in the doc, otherwise we might have duplicates for the same 
        entity that got split across chunks. Used in inference only."""
        if not spans:
            return []

        spans = sorted(spans, key=lambda x: (x["start"], x["end"]))
        merged = [spans[0]]

        for span in spans[1:]:
            last = merged[-1]

            if span["label"] == last["label"] and span["start"] <= last["end"]:
                last["end"] = max(last["end"], span["end"])
            else:
                merged.append(span)

        return merged

    def _char_span_to_token_span(self, 
                                 doc: MutableDocument, 
                                 start_char: int, 
                                 end_char: int) -> Optional[tuple[int, int]]:
        """Compatibility with SpaCy tokenization - convert character span to token span. 
        Used in inference only."""
        spacy_doc = doc._delegate
        # Prefer strict/inner alignment first
        span = spacy_doc.char_span(start_char, end_char, alignment_mode="contract")
        # This very rarely fails
        # If it does, we've got expand then some manual token offset checking as a final fallback.
        if span is None:
            span = spacy_doc.char_span(start_char, end_char, alignment_mode="expand")
        if span is not None:
            return span.start, span.end

        # derive token indices from token character offsets.
        token_start = None
        token_end = None
        for tok in spacy_doc:
            tok_start = tok.idx
            tok_end = tok.idx + len(tok)

            if tok_end <= start_char:
                continue
            if tok_start >= end_char and token_end is not None:
                break

            if token_start is None and tok_end > start_char:
                token_start = tok.i
            if tok_start < end_char:
                token_end = tok.i + 1

        if token_start is None or token_end is None or token_start >= token_end:
            return None
        return token_start, token_end

    def _preprocess_tokens(self, tokens: list[MutableToken]) -> str:
        tokens_raw = ' '.join(tkn.text.lower() for tkn in tokens).strip()
        return tokens_raw.replace(' ', self.config.general.separator)

    def predict_entities(self, doc: MutableDocument,
                         ents: list[MutableEntity] | None = None
                         ) -> list[MutableEntity]:
        """Detect candidates for concepts - linker will then be able
        to do the rest. It adds `entities` to the doc.ner_ents and each
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
        # Keep offset generation in the same coordinate space as spaCy char_span.
        text = doc._delegate.text
        input_ids, attention_masks, offset_mappings, chunk_char_starts, _ = self._chunk_and_encode(text)

        self.model.eval()
        with torch.no_grad():
            input_ids = input_ids.to(self.device)
            attention_masks = attention_masks.to(self.device)

            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_masks
            )
            predictions = outputs.logits.argmax(dim=-1).cpu().tolist()
            
        all_spans = []
        for preds, offsets_chunk, char_start in zip(
            predictions,
            offset_mappings,
            chunk_char_starts
        ):
            spans = self._decode_chunk(preds, offsets_chunk, char_start)
            all_spans.extend(spans)
        final_spans = self._merge_spans(all_spans)
        
        ner_ents = []
        seen_token_spans = set()
        for span in final_spans:
            token_char_end = max(span["start"], span["end"] - 1)
            tokens = doc.get_tokens(span["start"], token_char_end)
            if not tokens:
                continue

            # I'm not sure if this is required or beneficial.
            # Essentially in the case where you don't require link candidates
            # We only need the detected name, no candidates. So the span that is detected
            # by the model can potentially be linked
            if not self.cnf_ner.require_link_candidates:
                token_start = tokens[0].base.index
                token_end = tokens[-1].base.index + 1
                span_key = (token_start, token_end)
                if span_key not in seen_token_spans:
                    ent = self.tokenizer.create_entity(
                        doc,
                        token_start,
                        token_end,
                        text[span["start"]:span["end"]]
                    )
                    if ent:
                        ner_ents.append(ent)
                        seen_token_spans.add(span_key)

            for i in range(len(tokens)):
                for j in range(i + 1, len(tokens) + 1):
                    sub_tokens = tokens[i:j]
                    preprocessed_sub_name = self._preprocess_tokens(sub_tokens)
                    if preprocessed_sub_name not in self.cdb.name2info:
                        continue

                    token_start = sub_tokens[0].base.index
                    token_end = sub_tokens[-1].base.index + 1
                    span_key = (token_start, token_end)
                    if span_key in seen_token_spans:
                        continue

                    ent = None
                    if not self.cnf_ner.require_link_candidates:
                        detected_name = text[
                            sub_tokens[0].base.char_index:
                            sub_tokens[-1].base.char_index + len(sub_tokens[-1].text)
                        ]
                        ent = self.tokenizer.create_entity(
                            doc,
                            token_start,
                            token_end,
                            detected_name
                        )
                    else:
                        ent = annotate_name(
                            self.tokenizer,
                            preprocessed_sub_name,
                            sub_tokens,
                            doc,
                            self.cdb,
                            len(ner_ents),
                            'concept'
                        )

                    if ent:
                        detected_name = text[
                            sub_tokens[0].base.char_index:
                            sub_tokens[-1].base.char_index + len(sub_tokens[-1].text)
                        ]
                        ner_ents.append(ent)
                        seen_token_spans.add(span_key)
        return ner_ents

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]) -> 'TransformerNER':
        return cls(tokenizer, cdb)
    
    def serialise_to(self, folder_path: str) -> None:
        os.makedirs(folder_path, exist_ok=True)
        model_folder = os.path.join(folder_path, self._MODEL_FOLDER_NAME)
        os.makedirs(model_folder, exist_ok=True)

        torch.save(
            # TODO: save gracefully when NER model done
            self.model.state_dict(),
            os.path.join(model_folder, self._MODEL_STATE_FILE_NAME),
        )

    @classmethod
    def deserialise_from(
        cls, folder_path: str, **init_kwargs
    ) -> "NER":
        cdb = init_kwargs["cdb"]
        tokenizer = init_kwargs["tokenizer"]
        ner = cls(tokenizer, cdb)

        model_state_path = os.path.join(
            folder_path, cls._MODEL_FOLDER_NAME, cls._MODEL_STATE_FILE_NAME
        )

        # TODO: handle this gracefully when NER model done
        if os.path.exists(model_state_path):
            state_dict = torch.load(model_state_path, map_location=ner.device)
            ner.model.load_state_dict(state_dict)

        return ner