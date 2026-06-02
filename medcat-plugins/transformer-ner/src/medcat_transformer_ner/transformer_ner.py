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
from transformers import AutoTokenizer, AutoModelForTokenClassification, get_constant_schedule_with_warmup
from medcat_transformer_ner.transformer_ner_model import ModelForBinaryNER
from medcat_transformer_ner.config import TransformerNER
import logging
import os
import torch

logger = logging.getLogger(__name__)


class NER(AbstractEntityProvidingComponent, TrainableComponent, AbstractManualSerialisable):
    name = 'transformer_ner'

    comp_name = "transformer_ner"
    _MODEL_FOLDER_NAME = "transformer_ner_model"

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
            "I-ENT": 2,
            "E-ENT": 3,
            "S-ENT": 4
        }
        self.id2label = {v: k for k, v in self.label2id.items()}
        self._model_init_kwargs = dict()
        self.load_transformers(self.cnf_ner.language_model_name)
        self.max_token_length = self.cnf_ner.max_token_length
        self.overlap_chunking = self.cnf_ner.overlap_chunking

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
                clean_up_tokenization_spaces=False
            )
            self.model = ModelForBinaryNER(
                embedding_model_name=model_source,
                id2label=self.id2label,
                **model_init_kwargs
            )
            
            self.model.eval()
            self.device = torch.device(
                self.cnf_ner.gpu_device
                or ("cuda" if torch.cuda.is_available() else "cpu")
            )
            self.model.to(self.device)
            self._loaded_model_source = model_source
            self._loaded_model_init_kwargs = model_init_kwargs
            self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=1e-5, weight_decay=0.001)
            self.scheduler = get_constant_schedule_with_warmup(
                self.optimizer,
                num_warmup_steps=20,
            )
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
                    ent_end = ent.base.end_char_index # make end exclusive

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
                    ent_token_indices = []
                    for i, (token_start, token_end) in enumerate(offsets_chunk):
                        if token_start == token_end:
                            continue
                        if token_start < ent["end"] and token_end > ent["start"]:
                            ent_token_indices.append(i)

                    if not ent_token_indices:
                        continue

                    if len(ent_token_indices) == 1:
                        labels[ent_token_indices[0]] = self.label2id["S-ENT"]
                        continue

                    labels[ent_token_indices[0]] = self.label2id["B-ENT"]
                    labels[ent_token_indices[-1]] = self.label2id["E-ENT"]
                    for i in ent_token_indices[1:-1]:
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
            
            # debugging
            # start_logits = outputs.start_logits
            # end_logits = outputs.end_logits
            # predictions = outputs.logits.argmax(dim=-1).cpu().tolist()
            # for chunk_input_ids, chunk_pred_ids, chunk_label_ids, chunk_start_logits, chunk_end_logits in (
            #     zip(
            #         input_ids.cpu().tolist(),
            #         predictions,
            #         labels.cpu().tolist(),
            #         start_logits.detach().cpu(),
            #         end_logits.detach().cpu(),
            #     )
            # ):
            #     for input_id, label_id, pred_id, start_logit, end_logit in (
            #         zip(chunk_input_ids, chunk_label_ids, chunk_pred_ids, chunk_start_logits, chunk_end_logits)
            #         ):
            #         token = self.transformer_tokenizer.convert_ids_to_tokens(input_id)
            #         pred_label = self.id2label[pred_id] if pred_id in self.id2label else "N/A"
            #         true_label = self.id2label[label_id] if label_id in self.id2label else "N/A"
            #         start_prob = torch.sigmoid(start_logit).item()
            #         end_prob = torch.sigmoid(end_logit).item()
            #         print(f"[{token}, {true_label}, {pred_label}, start_logit={start_prob:.4f}, end_logit={end_prob:.4f}]")
            print(f"CRF Loss: {outputs.crf_loss.item()}")
            print(f"Start Loss: {outputs.start_loss.item()}")
            print(f"End Loss: {outputs.end_loss.item()}")
            # import sys
            # sys.exit(0)
            loss = outputs.loss
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(),
                1.0
            )
            self.optimizer.step()
            self.scheduler.step()
            print(f"NER training step - loss: {loss.item()}")
            logger.debug("NER training step - loss: ", 
                         loss.item())

    def _decode_chunk(self, preds, offsets_chunk, chunk_char_start):
        """For inference only. Decode a single chunk of predictions into entity 
        spans, then merge them across chunks."""
        spans = []
        current = None
        # print("Predictions: ", preds)
        for pred_id, (tok_start, tok_end) in zip(preds, offsets_chunk):

            # skip padding / special tokens
            if (tok_start, tok_end) == (0, 0):
                continue

            label = self.id2label[pred_id]

            # If label is "O", close any open entity span and move on.
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

            # B starts a new span
            if prefix == "B":
                if current is not None:
                    spans.append(current)
                current = {
                    "start": abs_start,
                    "end": abs_end,
                    "label": ent_type
                }

            # I continues
            elif prefix == "I":
                if current is not None and current["label"] == ent_type:
                    current["end"] = abs_end
                else:
                    # Broken sequence -> treat as a new span.
                    current = {
                        "start": abs_start,
                        "end": abs_end,
                        "label": ent_type
                    }

            # E closes
            elif prefix == "E":
                if current is not None and current["label"] == ent_type:
                    current["end"] = abs_end
                    spans.append(current)
                    current = None
                else:
                    # Broken sequence -> treat standalone E as a single-token span.
                    spans.append({
                        "start": abs_start,
                        "end": abs_end,
                        "label": ent_type
                    })

            # S is a single token span
            elif prefix == "S":
                if current is not None:
                    spans.append(current)
                    current = None
                spans.append({
                    "start": abs_start,
                    "end": abs_end,
                    "label": ent_type
                })

        if current is not None:
            spans.append(current)

        return spans

    def _merge_spans(self, spans, text: str) -> list[dict]:
        """Merge spans across chunk boundaries. This is required before creating 
        entities in the doc, otherwise we might have duplicates for the same 
        entity that got split across chunks. Used in inference only."""
        if not spans:
            return []

        spans = sorted(spans, key=lambda x: (x["start"], x["end"]))
        merged = [spans[0]]

        for span in spans[1:]:
            last = merged[-1]
            gap_text = text[last["end"]:span["start"]]
            gap_is_soft_separator = not gap_text.strip() or gap_text.strip() in {"/", "-"}

            if span["label"] == last["label"] and (
                span["start"] <= last["end"] or gap_is_soft_separator
            ):
                last["end"] = max(last["end"], span["end"])
            else:
                merged.append(span)

        return merged
    
    
    # Build segments in two modes:
    # 1) keep half separators inside tokens, 2) split on half separators.
    def _build_segments(self, 
                        split_chars: set[str], 
                        detected_string: str, 
                        detected_start: int, 
                        detected_end: int) -> list[tuple[int, int]]:
        segs = []
        seg_start = None
        for idx, ch in enumerate(detected_string):
            if ch in split_chars:
                if seg_start is not None:
                    segs.append((detected_start + seg_start, detected_start + idx))
                    seg_start = None
            elif seg_start is None:
                seg_start = idx
        if seg_start is not None:
            segs.append((detected_start + seg_start, detected_end))
        return segs

    def _char_span_to_token_span(
        self,
        doc: MutableDocument,
        start_char: int,
        end_char: int,
    ) -> Optional[tuple[int, int]]:
        token_start = None
        token_end = None

        for token in doc:
            if token.end_char_index <= start_char:
                continue
            if token.char_index >= end_char:
                break

            if token_start is None:
                token_start = token.index
            token_end = token.index + 1

        if token_start is None or token_end is None:
            return None

        return token_start, token_end
       
    def _span_inference(self, spans: list[dict], 
                        doc: MutableDocument, 
                        text: str) -> list[MutableEntity]:
        ner_ents = []
        seen_token_spans = set()
        logger.debug("Num detected spans: %s", len(spans))
        # print(f"Num detected spans: {len(spans)}")
        for span in spans:
            detected_start = span["start"]
            detected_end = span["end"]
            detected_string = text[detected_start:detected_end]
            if not detected_string:
                continue
            # print(f"Detected span: [{detected_start}, {detected_end}] {repr(detected_string)}")
            logger.debug(
                "Detected span: [%s, %s] %r",
                detected_start,
                detected_end,
                detected_string,
            )

            token_span = self._char_span_to_token_span(doc, detected_start, detected_end)
            if token_span is None:
                continue

            token_start, token_end = token_span
            if self.cnf_ner.use_prefix_token:
                token_start = token_start - 1 if token_start > 0 else token_start
            # Loop through all contiguous token subspans [i:j]
            for i in range(token_start, token_end):
                for j in range(i + 1, token_end + 1):
                    span_key = (i, j)
                    if span_key in seen_token_spans:
                        continue
                    
                    sub_tokens = list(doc[i:j])
                    # there might be more cleaning required here
                    detected_name = self.config.general.separator.join(
                        token.text.lower() for token in sub_tokens
                    )
                    ent = None
                    if detected_name in self.cdb.name2info:
                        ent = annotate_name(
                            self.tokenizer, 
                            detected_name, 
                            sub_tokens,
                            doc, 
                            self.cdb, 
                            len(ner_ents), 
                            detected_name
                        )
                    elif not self.cnf_ner.require_link_candidates:
                        ent = self.tokenizer.create_entity(
                            doc,
                            i,
                            j,
                            detected_name,
                        )
                    
                    if ent:
                        # print(
                        #     f"Created entity: raw_text={repr(ent.text)}, detected_name={repr(ent.detected_name)}, tokens=[{i}, {j}]"
                        # )
                        logger.debug(
                            "Created entity: %r tokens [%s, %s]",
                            ent.text,
                            i,
                            j,
                            ent.base.start_char_index,
                            ent.base.end_char_index,
                        )
                        ner_ents.append(ent)
                        seen_token_spans.add(span_key)
        
        return ner_ents

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
        text = doc.text
        input_ids, attention_masks, offset_mappings, chunk_char_starts, _ = self._chunk_and_encode(text)

        self.model.eval()
        with torch.no_grad():
            input_ids = input_ids.to(self.device)
            attention_masks = attention_masks.to(self.device)
            
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_masks
            )
            predictions = outputs.predictions.cpu().tolist()
        # debugging
        # for inputs, preds in zip(input_ids.cpu().tolist(), predictions):
        #     for input_id, pred_id in zip(inputs, preds):
        #         token = self.transformer_tokenizer.convert_ids_to_tokens(input_id)
        #         pred_label = self.id2label[pred_id] if pred_id in self.id2label else "N/A"
        #         print(f"[{token}, {pred_label}]")
        # import sys
        # sys.exit(0)
            
        all_spans = []
        for preds, offsets_chunk, char_start in zip(
            predictions,
            offset_mappings,
            chunk_char_starts
        ):
            spans = self._decode_chunk(preds, offsets_chunk, char_start)
            all_spans.extend(spans)
        final_spans = self._merge_spans(all_spans, text)
        
        return self._span_inference(final_spans, doc, text)

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]) -> 'TransformerNER':
        return cls(tokenizer, cdb)
    
    def serialise_to(self, folder_path: str) -> None:
        os.makedirs(folder_path, exist_ok=True)
        model_folder = os.path.join(folder_path, self._MODEL_FOLDER_NAME)
        os.makedirs(model_folder, exist_ok=True)
        
        # Save in HuggingFace format for forward compatibility.
        self.model.save_pretrained(model_folder)

    @classmethod
    def deserialise_from(
        cls, folder_path: str, **init_kwargs
    ) -> "NER":
        cdb = init_kwargs["cdb"]
        tokenizer = init_kwargs["tokenizer"]
        ner = cls(tokenizer, cdb)
        model_folder = os.path.join(
            folder_path, cls._MODEL_FOLDER_NAME
        )
        config_path = os.path.join(model_folder, "config.json")
        weights_path = os.path.join(model_folder, "pytorch_model.bin")
        if not os.path.exists(config_path) or not os.path.exists(weights_path):
            raise FileNotFoundError(
                "Could not find transformer-ner checkpoint files in "
                f"{model_folder}. Expected both config.json and pytorch_model.bin."
            )

        # ner.model = AutoModelForTokenClassification.from_pretrained(model_folder)
        ner.model = ModelForBinaryNER.from_pretrained(
            model_folder,
            device=ner.device,
        )
        ner.optimizer = torch.optim.AdamW(ner.model.parameters(), lr=1e-5, weight_decay=0.001)
        ner.scheduler = get_constant_schedule_with_warmup(ner.optimizer, num_warmup_steps=20)
        ner.model.to(ner.device)
        ner.model.eval()

        return ner