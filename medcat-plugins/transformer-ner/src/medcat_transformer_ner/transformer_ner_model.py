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

class ModelForBinaryNER(nn.Module):
    """Wrapper around a Hugging Face transformer for transformer-based NER.

    
    """

    def __init__(
        self,
        embedding_model_name: str,
        top_n_layers_to_unfreeze: int = -1,
        device: Optional[Union[str, torch.device]] = None,
    ) -> None:
        super().__init__()
        self.language_model = AutoModel.from_pretrained(embedding_model_name)
        self.base_model_name = self.language_model.name_or_path

        # TODO: rest of logic here

        self.top_n_layers_to_unfreeze = top_n_layers_to_unfreeze

        hidden_size = self.language_model.config.hidden_size
        
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

        # TODO: logic required

        pass

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
    ) -> "ModelForBinaryNER":
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