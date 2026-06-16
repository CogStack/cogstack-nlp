from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, Union
from torch import Tensor, nn
from torchcrf import CRF
from transformers import AutoModelForTokenClassification
import json
import logging
import torch

logger = logging.getLogger(__name__)

class ModelForBinaryNER(nn.Module):
    """Wrapper around a Hugging Face transformer for transformer-based NER.

    The architecture is: transformer backbone -> linear classifier -> CRF.
    """
    # for mypy checking
    label_is_start: Tensor
    label_is_end: Tensor

    def __init__(
        self,
        embedding_model_name: str,
        id2label: dict[int, str],
        num_labels: int = 5,
        top_n_layers_to_unfreeze: int = -1,
        device: Optional[Union[str, torch.device]] = None,
        aux_loss_weight: float = 0.5,
    ) -> None:
        super().__init__()
        self.num_labels = num_labels
        self.aux_loss_weight = aux_loss_weight
        self.id2label = id2label
        self.language_model = AutoModelForTokenClassification.from_pretrained(
            embedding_model_name,
            num_labels=self.num_labels,
        )
        # Make sure hidden states are available for the auxiliary heads.
        self.language_model.config.output_hidden_states = True
        self.base_model_name = self.language_model.config.name_or_path
        
        # For the auxiliary start/end position heads, we use the hidden states 
        # from the last layer of the transformer.
        hidden_size = self.language_model.config.hidden_size
        self.start_head = nn.Linear(hidden_size, 1)
        self.end_head = nn.Linear(hidden_size, 1)
        
        # For state transitions
        self.crf = CRF(num_tags=self.num_labels, batch_first=True)
        
        # Build boundary lookup tables from BIOES label names.
        # This is future proof in the sense that "B" and "E" would still be the same
        # for multiple different types of entities.
        start_flags = []
        end_flags = []
        for i in range(self.num_labels):
            label = self.id2label[i]
            prefix = label.split("-", 1)[0]

            start_flags.append(1.0 if prefix == "B" else 0.0)
            end_flags.append(1.0 if prefix == "E" else 0.0)
            
        self.register_buffer("label_is_start", torch.tensor(start_flags, dtype=torch.float))
        self.register_buffer("label_is_end", torch.tensor(end_flags, dtype=torch.float))

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

    def forward(self, **inputs) -> Any:
        labels: Optional[Tensor] = inputs.pop("labels", None)
        attention_mask: Tensor = inputs["attention_mask"]

        outputs = self.language_model(**inputs, 
                                      return_dict=True, 
                                      output_hidden_states=True)
        emissions = outputs.logits
        hidden_states = outputs.hidden_states[-1]  # the last layer's hidden states for the start/end heads
        
        # Linear classifiers for boundary heads
        start_logits = self.start_head(hidden_states).squeeze(-1)  # [B, T]
        end_logits = self.end_head(hidden_states).squeeze(-1)      # [B, T]

        # CRF can't handle -100 labels so this handles it
        loss = None
        crf_loss = None
        start_loss = None
        end_loss = None
        
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
            
            # Auxiliary start/end targets
            start_targets, end_targets = self._build_boundary_targets(labels)

            # Use the standard attention mask, but exclude -100 positions
            aux_mask = valid_mask & (labels != -100)

            start_loss = self._masked_bce_loss(start_logits, start_targets, aux_mask)
            end_loss = self._masked_bce_loss(end_logits, end_targets, aux_mask)

            loss = crf_loss + self.aux_loss_weight * (start_loss + end_loss)

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
            start_loss=start_loss,
            end_loss=end_loss,
            logits=emissions,
            start_logits=start_logits,
            end_logits=end_logits,
            predictions=decoded_tensor,
            decoded_sequences=decoded_sequences,
        )

    def _masked_bce_loss(self, logits: Tensor, targets: Tensor, mask: Tensor) -> Tensor:
        """
        Normal BCE doesn't handle masking (i.e. handling [-100]), 
        so this implements a masked version.
        """
        loss_fn = nn.BCEWithLogitsLoss(reduction="none")
        loss = loss_fn(logits, targets.float())
        loss = loss * mask.float()

        denom = mask.float().sum().clamp_min(1.0)
        return loss.sum() / denom
    
    def _build_boundary_targets(self, labels: Tensor) -> tuple[Tensor, Tensor]:
        """
        Convert BIOES token labels into binary start/end targets.
        - start = 1 for B-*, (and maybe S-*)
        - end   = 1 for E-*, (and maybe S-*)
        """
        safe_labels = labels.clone()
        safe_labels[safe_labels == -100] = 0

        start_targets = self.label_is_start[safe_labels].to(labels.device)
        end_targets = self.label_is_end[safe_labels].to(labels.device)

        start_targets = start_targets.masked_fill(labels == -100, 0.0)
        end_targets = end_targets.masked_fill(labels == -100, 0.0)

        return start_targets, end_targets

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
            "aux_loss_weight": self.aux_loss_weight,
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
            config.update(kwargs)
            model = cls(device=target_device, **config)
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