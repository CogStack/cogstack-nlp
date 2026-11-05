from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, Union
from torch import Tensor, nn
from torchcrf import CRF
from transformers import AutoModel
import json
import logging
import torch

logger = logging.getLogger(__name__)

class ModelForBinaryNER(nn.Module):
    """Wrapper around a Hugging Face transformer for transformer-based NER.

    The architecture is: transformer backbone -> linear classifier -> CRF.
    """
    class_weights: Tensor

    def __init__(
        self,
        embedding_model_name: str,
        id2label: dict[int, str],
        num_labels: int = 5,
        top_n_layers_to_unfreeze: int = -1,
        device: Optional[Union[str, torch.device]] = None,
        class_weights: Optional[dict[str, float]] = None,
        crf_loss_weight: float = 1.0,
    ) -> None:
        super().__init__()
        self.num_labels = num_labels
        self.id2label = id2label
        self.class_weights_dict = dict(class_weights or {})
        self.crf_loss_weight = crf_loss_weight
        self.language_model = AutoModel.from_pretrained(
            embedding_model_name,
            trust_remote_code=True,  # generally harmless for standard models
        )

        self.base_model_name = self.language_model.config.name_or_path
        hidden_size = self.language_model.config.hidden_size

        # Main token classification head: CRF emissions
        self.classifier = nn.Linear(hidden_size, self.num_labels)
        
        # For state transitions
        self.crf = CRF(num_tags=self.num_labels, batch_first=True)
        
        # non-persistent so that existing checkpoints still load
        self.register_buffer("class_weights",
                             self._build_class_weights_tensor(),
                             persistent=False)

        target_device = self._resolve_device(device)
        self.to(target_device)

    def _build_class_weights_tensor(self) -> Tensor:
        """cross_entropy needs a 1-D tensor indexed by label id; labels
        without a given weight default to 1.0."""
        return torch.tensor(
            [self.class_weights_dict.get(self.id2label[i], 1.0)
             for i in range(self.num_labels)],
            dtype=torch.float)

    def set_class_weights(self, class_weights: dict[str, float]) -> None:
        """Update the class weights (by label name) on an already built model.
        If all weights are 0 the weighted cross entropy is skipped (CRF loss
        only)."""
        self.class_weights_dict = dict(class_weights)
        self.class_weights = self._build_class_weights_tensor().to(self.device)

    @staticmethod
    def _resolve_device(device: Optional[Union[str, torch.device]]) -> torch.device:
        if device is None:
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device)

    @property
    def device(self) -> torch.device:
        return next(self.parameters()).device

    def forward(self, **inputs) -> Any:
        labels: Optional[Tensor] = inputs.pop("labels", None)
        attention_mask: Tensor = inputs["attention_mask"]

        outputs = self.language_model(**inputs, 
                                      return_dict=True, 
                                      output_hidden_states=True)
        hidden_states = outputs.last_hidden_state
        # Main token-classification logits, used as CRF emissions
        emissions = self.classifier(hidden_states)

        # CRF can't handle -100 labels so this handles it
        loss = None
        crf_loss = None
        weighted_ce_loss = None
        
        valid_mask = attention_mask.bool()
        
        if labels is not None:
            labels = labels.long()
            
            # CRF can't handle -100 labels, so we mask them out.
            crf_mask = valid_mask & (labels != -100)
            safe_labels = labels.clone()
            safe_labels[safe_labels == -100] = 0

            # CRF requires the first timestep to be valid for every sequence.
            crf_mask[:, 0] = True

            # CRF also requires each sequence to have at least one valid timestep.
            no_valid_tokens = ~crf_mask.any(dim=1)
            if no_valid_tokens.any():
                crf_mask[no_valid_tokens, 0] = True

            safe_labels[~crf_mask] = 0
            crf_loss = -self.crf(
                emissions,
                safe_labels,
                mask=crf_mask,
                reduction="token_mean",
            )

            loss = self.crf_loss_weight * crf_loss

            # The CRF NLL is sequence-level and cannot be weighted per class,
            # so class weights are applied via a token-level cross entropy
            # on the emissions, added to the (scaled) CRF loss.
            use_ce = self.class_weights.sum() > 0
            if use_ce:
                weighted_ce_loss = nn.functional.cross_entropy(
                    emissions.reshape(-1, self.num_labels),
                    labels.masked_fill(~valid_mask, -100).reshape(-1),
                    weight=self.class_weights,
                    ignore_index=-100,
                )
                loss = loss + weighted_ce_loss

        decoded_sequences = None
        decoded_tensor = None
        # Decoding is only needed for inference.
        # Skip it during training to avoid unnecessary CRF calls
        if labels is None:
            decoded_sequences = self.crf.decode(emissions, mask=valid_mask)
            decoded_tensor = torch.zeros(
                emissions.shape[:2],
                dtype=torch.long,
                device=emissions.device,
            )
            for row_idx, seq in enumerate(decoded_sequences):
                if seq:
                    decoded_tensor[row_idx, : len(seq)] = torch.tensor(
                        seq,
                        dtype=torch.long,
                        device=emissions.device,
                    )

        return SimpleNamespace(
            loss=loss,
            crf_loss=crf_loss,
            weighted_ce_loss=weighted_ce_loss,
            logits=emissions,
            predictions=decoded_tensor,
            decoded_sequences=decoded_sequences,
        )

    def _freeze_all_parameters(self) -> None:
        for param in self.language_model.parameters():
            param.requires_grad = False

        # The classification head always needs to be trainable
        for param in self.language_model.classifier.parameters():
            param.requires_grad = True

        # Same for the CRF
        for param in self.crf.parameters():
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

        base = self.language_model.base_model
        # BERT-likes
        if hasattr(base, "encoder") and hasattr(base.encoder, "layer"):
            layers = base.encoder.layer
        # DistilBERT-likes
        elif hasattr(base, "transformer") and hasattr(base.transformer, "layer"):
            layers = base.transformer.layer
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
            "num_labels": self.num_labels,
            "id2label": self.id2label,
            "class_weights": self.class_weights_dict,
            "crf_loss_weight": self.crf_loss_weight,
        }
        with open(save_path / "config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    @classmethod
    def from_pretrained(
        cls,
        path_or_model_name: Union[str, Path],
        device: Optional[Union[str, torch.device]] = None,
        **kwargs,
    ) -> "ModelForBinaryNER":
        path = Path(path_or_model_name)
        config_path = path / "config.json"
        weights_path = path / "pytorch_model.bin"
        target_device = cls._resolve_device(device)

        # Local saved wrapper model.
        if config_path.exists() and weights_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)

            # because loading in turns int keys into strings
            if "id2label" in config:
                id2label: dict[int, str] = {}
                for key, value in config["id2label"].items():
                    id2label[int(key)] = value
                config["id2label"] = id2label
            # the auxiliary start/end loss was removed; tolerate old checkpoints
            config.pop("aux_loss_weight", None)
            config.pop("class_weighted_loss_coef", None)
            config.update(kwargs)
            model = cls(device=target_device, **config)
            state_dict = torch.load(weights_path, map_location="cpu")
            legacy_prefixes = ("start_head.", "end_head.")
            legacy_buffers = ("label_is_start", "label_is_end")
            state_dict = {
                k: v for k, v in state_dict.items()
                if not k.startswith(legacy_prefixes) and k not in legacy_buffers
            }
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