from pathlib import Path
from typing import Any, Iterator, Optional, Union
from medcat.storage.serialisables import AbstractSerialisable
from torch import Tensor, nn
from transformers import AutoModel, AutoTokenizer
from tqdm import tqdm
import json
import logging
import math
import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class ModelForEmbeddingLinking(nn.Module):
    """Wrapper around a Hugging Face transformer for embedding-based linking.

    The model applies mean pooling over token embeddings, optionally projects the
    pooled vector, and L2 normalizes the final embedding.
    """

    def __init__(
        self,
        embedding_model_name: str,
        use_projection_layer: bool = False,
        top_n_layers_to_unfreeze: int = -1,
        device: Optional[Union[str, torch.device]] = None,
    ) -> None:
        super().__init__()
        self.language_model = AutoModel.from_pretrained(embedding_model_name)
        self.base_model_name = self.language_model.name_or_path

        self.use_projection_layer = use_projection_layer
        self.top_n_layers_to_unfreeze = top_n_layers_to_unfreeze

        hidden_size = self.language_model.config.hidden_size
        if self.use_projection_layer:
            self.projection_layer = nn.Linear(hidden_size, hidden_size)

        self._freeze_all_parameters()
        self.unfreeze_top_n_lm_layers(self.top_n_layers_to_unfreeze)

        target_device = self._resolve_device(device)
        self.to(target_device)

    @staticmethod
    def _resolve_device(device: Optional[Union[str, torch.device]]) -> torch.device:
        if device is None:
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device)

    @property
    def device(self) -> torch.device:
        return next(self.parameters()).device

    @staticmethod
    def masked_mean_pooling(token_embeddings: Tensor, mask: Tensor) -> Tensor:
        mask = mask.unsqueeze(-1).float()
        summed = torch.sum(token_embeddings * mask, dim=1)
        counts = torch.clamp(mask.sum(dim=1), min=1e-9)
        return summed / counts

    def forward(self, **inputs) -> Tensor:
        # Don't pass the mention_mask to the language model if it does exist
        mention_mask = inputs.pop("mention_mask", None)
        model_output = self.language_model(**inputs)

        pooling_mask = (
            mention_mask if mention_mask is not None else inputs["attention_mask"]
        )
        sentence_embeddings = self.masked_mean_pooling(
            model_output.last_hidden_state, pooling_mask
        )

        if self.use_projection_layer:
            sentence_embeddings = self.projection_layer(sentence_embeddings)
        return F.normalize(sentence_embeddings, p=2, dim=1)

    def _freeze_all_parameters(self) -> None:
        for param in self.language_model.parameters():
            param.requires_grad = False

        if self.use_projection_layer:
            for param in self.projection_layer.parameters():
                param.requires_grad = True

    def unfreeze_top_n_lm_layers(self, n: int) -> None:
        # train all LM layers - each layer requires more data
        if n == -1:
            for param in self.language_model.parameters():
                param.requires_grad = True
            return

        # keep LM fully frozen - better with less data
        if n == 0:
            return

        # BERT-likes
        if hasattr(self.language_model, "encoder") and hasattr(
            self.language_model.encoder, "layer"
        ):
            layers = self.language_model.encoder.layer
        # DistilBERT-likes
        elif hasattr(self.language_model, "transformer") and hasattr(
            self.language_model.transformer, "layer"
        ):
            layers = self.language_model.transformer.layer
        else:
            raise ValueError("Unsupported LM architecture for layer unfreezing.")

        total_layers = len(layers)
        n = min(n, total_layers)
        for layer in layers[-n:]:
            for param in layer.parameters():
                param.requires_grad = True

    def save_pretrained(self, save_directory: Union[str, Path]) -> None:
        save_path = Path(save_directory)
        save_path.mkdir(parents=True, exist_ok=True)

        torch.save(self.state_dict(), save_path / "pytorch_model.bin")

        config = {
            "embedding_model_name": self.base_model_name,
            "use_projection_layer": self.use_projection_layer,
            "top_n_layers_to_unfreeze": self.top_n_layers_to_unfreeze,
        }
        with open(save_path / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    @classmethod
    def from_pretrained(
        cls,
        path_or_model_name: Union[str, Path],
        device: Optional[Union[str, torch.device]] = None,
        **kwargs,
    ) -> "ModelForEmbeddingLinking":
        path = Path(path_or_model_name)
        config_path = path / "config.json"
        weights_path = path / "pytorch_model.bin"
        target_device = cls._resolve_device(device)

        # Local saved wrapper model.
        if config_path.exists() and weights_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)

            config.update(kwargs)
            model = cls(**config)
            state_dict = torch.load(weights_path, map_location="cpu")
            model.load_state_dict(state_dict)
            model.to(target_device)
            return model

        # Hugging Face model id/path.
        model = cls(
            embedding_model_name=str(path_or_model_name),
            device=target_device,
            **kwargs,
        )
        return model


class ContextModel(AbstractSerialisable):
    """Encapsulates embedding model/tokenizer loading and CDB embedding creation."""

    def __init__(
        self,
        cdb,
        linking_config,
        separator: str,
        model_init_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        self.cdb = cdb
        self.cnf_l = linking_config
        self.separator = separator
        self._model_init_kwargs = dict(model_init_kwargs or {})
        self.max_length = self.cnf_l.max_token_length
        self.device = torch.device(
            self.cnf_l.gpu_device or ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self._refresh_cdb_keys()
        self._cui_keys = list(self.cdb.cui2info)
        self._loaded_model_source: Optional[str] = None
        self._loaded_model_init_kwargs: Optional[dict[str, Any]] = None
        self.load_transformers(self.cnf_l.embedding_model_name)

    def _batch_data(self, data, batch_size=512) -> Iterator[list]:
        for i in range(0, len(data), batch_size):
            yield data[i : i + batch_size]

    def _refresh_cdb_keys(self) -> None:
        """Refresh key caches from current CDB state.

        This is required after in initialisation and for training-time CDB
        mutations where new names/CUIs be introduced.
        """
        self._name_keys = list(self.cdb.name2info)
        self._cui_keys = list(self.cdb.cui2info)

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

    def load_transformers(self, embedding_model_name: Union[str, Path]) -> None:
        """Load tokenizer/model from local path or Hugging Face model id."""
        model_source = self._resolve_model_source(embedding_model_name)
        model_init_kwargs = self._get_model_init_kwargs()
        if (
            not hasattr(self, "model")
            or not hasattr(self, "tokenizer")
            or model_source != self._loaded_model_source
            or model_init_kwargs != self._loaded_model_init_kwargs
        ):
            self.cnf_l.embedding_model_name = str(embedding_model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(model_source)
            self.model = ModelForEmbeddingLinking.from_pretrained(
                model_source, **model_init_kwargs
            )
            self.model.eval()
            self.device = torch.device(
                self.cnf_l.gpu_device
                or ("cuda" if torch.cuda.is_available() else "cpu")
            )
            self.model.to(self.device)
            self._loaded_model_source = model_source
            self._loaded_model_init_kwargs = model_init_kwargs
            logger.debug(
                "Loaded embedding model: %s (resolved source: %s) with kwargs=%s " \
				"on device: %s",
                embedding_model_name,
                model_source,
                model_init_kwargs,
                self.device,
            )

    def _build_mention_mask_from_char_spans(
        self,
        batch_dict: dict[str, Tensor],
        mention_char_spans: list[tuple[int, int]],
        device: torch.device,
    ) -> Tensor:
        """
        Convert character-level mention spans into a token-level mask.

        Args:
                batch_dict: tokenizer output with 'offset_mapping'
                mention_char_spans: list of (start_char, end_char) per example
                device: torch device

        Returns:
                mask: [batch_size, seq_len] float Tensor, 1.0 for mention tokens, 
                0.0 otherwise
        """
        offset_mapping = batch_dict["offset_mapping"]  # [B, max_token_length, 2]
        batch_size, seq_len, _ = offset_mapping.shape
        mask = torch.zeros((batch_size, seq_len), dtype=torch.float32, device=device)

        for i, (mention_start, mention_end) in enumerate(mention_char_spans):
            # For each token in the sequence
            for j in range(seq_len):
                token_start, token_end = offset_mapping[i, j].tolist()
                # Skip padding tokens
                if token_end == 0 and token_start == 0:
                    continue
                # Check if token overlaps mention span
                if token_end > mention_start and token_start < mention_end:
                    mask[i, j] = 1.0

        return mask

    def embed(
        self,
        to_embed: list[str],
        mention_spans: Optional[list[tuple[int, int]]] = None,
        device: Optional[torch.device] = None,
    ) -> Tensor:
        """Embed a list of input strings."""
        target_device = device or self.device
        # we don't need offset mapping when just embedding potential labels
        need_offsets_mapping = (
            self.cnf_l.use_mention_attention and mention_spans is not None
        )

        batch_dict = self.tokenizer(
            to_embed,
            max_length=self.max_length,
            padding=True,
            truncation=True,
            return_tensors="pt",
            return_offsets_mapping=need_offsets_mapping,
        ).to(target_device)

        mention_mask = None
        if mention_spans is not None:
            mention_mask = self._build_mention_mask_from_char_spans(
                batch_dict,
                mention_spans,
                target_device,
            )
            batch_dict["mention_mask"] = mention_mask

        # Keep tokenizer-only metadata out of model forward kwargs.
        batch_dict.pop("offset_mapping", None)

        outputs = self.model(**batch_dict)
        return outputs.half()

    def embed_cuis(
        self, embedding_model_name: Optional[Union[str, Path]] = None
    ) -> None:
        """Create embeddings for each CUI's longest name and store in CDB.

        If ``embedding_model_name`` is provided, switch/load that model first.
        Otherwise, reuse the currently loaded model (training-friendly default).
        """
        target_model = embedding_model_name or self.cnf_l.embedding_model_name
        self._refresh_cdb_keys()  # ensure _cui_keys is up to date before embedding
        self.load_transformers(target_model)

        cui_names = [self.cdb.get_name(cui) for cui in self._cui_keys]
        total_batches = math.ceil(len(cui_names) / self.cnf_l.embedding_batch_size)
        all_embeddings = []
        for names in tqdm(
            self._batch_data(cui_names, self.cnf_l.embedding_batch_size),
            total=total_batches,
            desc="Embedding cuis' preferred names",
        ):
            with torch.no_grad():
                names_to_embed = [name.replace(self.separator, " ") for name in names]
                embeddings = self.embed(names_to_embed, device=self.device)
                all_embeddings.append(embeddings.cpu())

        all_embeddings_matrix = torch.cat(all_embeddings, dim=0)
        self.cdb.addl_info["cui_embeddings"] = all_embeddings_matrix
        logger.debug("Embedding cui names done, total: %d", len(cui_names))

    def embed_names(
        self, embedding_model_name: Optional[Union[str, Path]] = None
    ) -> None:
        """Create embeddings for all names and store in CDB.

        If ``embedding_model_name`` is provided, switch/load that model first.
        Otherwise, reuse the currently loaded model (training-friendly default).
        """
        target_model = embedding_model_name or self.cnf_l.embedding_model_name
        self._refresh_cdb_keys()  # ensure _cui_keys is up to date before embedding
        self.load_transformers(target_model)

        names = self._name_keys
        total_batches = math.ceil(len(names) / self.cnf_l.embedding_batch_size)
        all_embeddings = []
        for batch_names in tqdm(
            self._batch_data(names, self.cnf_l.embedding_batch_size),
            total=total_batches,
            desc="Embedding names",
        ):
            with torch.no_grad():
                names_to_embed = [
                    name.replace(self.separator, " ") for name in batch_names
                ]
                embeddings = self.embed(names_to_embed, device=self.device)
                all_embeddings.append(embeddings.cpu())

        all_embeddings_matrix = torch.cat(all_embeddings, dim=0)
        self.cdb.addl_info["name_embeddings"] = all_embeddings_matrix
        logger.debug("Embedding names done, total: %d", len(names))
