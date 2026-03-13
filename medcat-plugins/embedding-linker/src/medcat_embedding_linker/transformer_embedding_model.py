from medcat.cdb import CDB
from medcat.config.config import Config
from medcat.storage.serialisables import AbstractSerialisable
from medcat.tokenizing.tokens import MutableEntity, MutableDocument
from torch import nn, Tensor
from transformers import AutoModel, AutoTokenizer
from typing import Iterator, Optional
from pathlib import Path
from tqdm import tqdm
from medcat_embedding_linker.config import EmbeddingLinking
import torch.nn.functional as F
import torch
import json
import math
import logging

logger = logging.getLogger(__name__)

class ModelForEmbeddingLinking(nn.Module):

    def __init__(
            self, 
            embedding_model_name: str, 
            use_projection_layer: bool = False, 
            top_n_layers_to_unfreeze: int = -1
            ):
        """A simple wrapper for the embedding model used in the embedding linker.
        This allows us to easily switch out the embedding model and use the same
        training and inference code.
        Args:
            embedding_model_name (str): The name/path of the embedding model to use.
            use_projection_layer (bool): Whether to use a projection layer on top of the embedding model.
            top_n_layers_to_unfreeze (int): The number of top layers of the embedding model to unfreeze for training. 
                Set to -1 to unfreeze all layers, 0 to freeze all layers, or any positive integer to unfreeze that many top layers.
        """
        super().__init__()
        self.language_model = AutoModel.from_pretrained(embedding_model_name)
        self.base_model_name = self.language_model.name_or_path
        hidden_size = self.language_model.config.hidden_size
        
        self.use_projection = use_projection_layer
        if self.use_projection:
            self.projection_layer = nn.Linear(hidden_size, hidden_size)
        self._freeze_all_parameters()
        self._unfreeze_top_n_lm_layers(top_n_layers_to_unfreeze)

    #Mean Pooling - Take attention mask into account for correct averaging
    def mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output.last_hidden_state # First element of model_output contains all token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()

        return torch.sum(token_embeddings * input_mask_expanded, 1) / \
            torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    def forward(self, **inputs):
        model_output = self.language_model(**inputs)
        sentence_embeddings = self.mean_pooling(model_output, inputs["attention_mask"])
        if self.use_projection:
            sentence_embeddings = self.projection_layer(sentence_embeddings)
        sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)
        return sentence_embeddings
    
    def _freeze_all_parameters(self):
        for param in self.language_model.parameters():
            param.requires_grad = False


    def _unfreeze_top_n_lm_layers(self, n: int):
        # Train everything in the LM
        if n == -1:
            for param in self.language_model.parameters():
                param.requires_grad = True
            return

        # Case 2: Freeze everything
        if n == 0:
            return

        # Case 3: Unfreeze top N layers - trade off time / performance MAYBE
        if hasattr(self.language_model, "encoder"): # e.g. encoder models like BERT
            layers = self.language_model.encoder.layer
        elif hasattr(self.language_model, "transformer"):  # e.g. DistilBERT
            layers = self.language_model.transformer.layer
        else:
            raise ValueError("Unsupported architecture for layer unfreezing.")

        total_layers = len(layers)
        n = min(n, total_layers)

        for layer in layers[-n:]:
            for param in layer.parameters():
                param.requires_grad = True

    @classmethod
    def from_pretrained(cls, path_or_model_name: str, device=None, **kwargs):
        path = Path(path_or_model_name)

        config_path = path / "config.json"
        weights_path = path / "pytorch_model.bin"

        # Locally saved model
        if config_path.exists() and weights_path.exists():

            with open(config_path) as f:
                config = json.load(f)

            model = cls(**config)

            state_dict = torch.load(weights_path, map_location=device)
            model.load_state_dict(state_dict)

            return model

        # Treat HuggingFace base model, probably download
        else:
            return cls(
                embedding_model_name=path_or_model_name,
                **kwargs
            )
        
    def save_pretrained(self, save_directory: str):
        save_directory = Path(save_directory)
        save_directory.mkdir(parents=True, exist_ok=True)

        torch.save(self.state_dict(), save_directory / "pytorch_model.bin")

        config = {
            "embedding_model_name": self.language_model.name_or_path,
            "use_projection_layer": not isinstance(self.projection, torch.nn.Identity),
        }

        with open(save_directory / "config.json", "w") as f:
            json.dump(config, f, indent=2)

class ContextModel(AbstractSerialisable):
    """
    ContextModel is a wrapper around the embedding model used in the embedding linker. 
    It handles the embedding of the CUI names and the context of the mentions, as well 
    as the training of the projection layer if used."""
    def __init__(
            self,
            config: Config,
            cnf_l: EmbeddingLinking,
            cdb: CDB,
            name_keys: list[str],
            cui_keys: list[str]
        ) -> None:
        self.config = config
        self.cnf_l = cnf_l
        self.cdb = cdb
        self._name_keys = name_keys
        self._cui_keys = cui_keys
        self.embedding_model = ModelForEmbeddingLinking(
            embedding_model_name=self.cnf_l.embedding_model_name,
            use_projection_layer=self.cnf_l.use_projection_layer,
            top_n_layers_to_unfreeze=self.cnf_l.top_n_layers_to_unfreeze
        )
        self.load_transformers(self.cnf_l.embedding_model_name)

    def _batch_data(self, data, batch_size=512) -> Iterator[list]:
        for i in range(0, len(data), batch_size):
            yield data[i : i + batch_size]

    def load_transformers(self, embedding_model_name: str) -> None:
        """Load the transformers model and tokenizer.
        Args:
            embedding_model_name (str): The name of the embedding model to load. 
            Default is "sentence-transformers/all-MiniLM-L6-v2"
        """
        if (
            not hasattr(self, "model")
            or not hasattr(self, "tokenizer")
            or embedding_model_name != self.cnf_l.embedding_model_name
        ):
            self.cnf_l.embedding_model_name = embedding_model_name
            self.model = ModelForEmbeddingLinking(
                embedding_model_name=embedding_model_name,
                use_projection_layer=self.cnf_l.use_projection_layer,
                top_n_layers_to_unfreeze=self.cnf_l.top_n_layers_to_unfreeze
            )
            self.tokenizer = AutoTokenizer.from_pretrained(self.model.base_model_name)
            gpu_device = self.cnf_l.gpu_device
            self.device = torch.device(
                gpu_device or ("cuda" if torch.cuda.is_available() else "cpu")
            )
            self.model.to(self.device)
            logger.debug(
                f"""Loaded embedding model: {embedding_model_name} 
                on device: {self.device}"""
            )

    def embed_cui_names(self, embedding_model_name: Optional[str] = None) -> None:
        """Obtain embeddings for all cuis longest names in the CDB using the specified
        embedding model and store them in the name2info.context_vectors
        Args:
            embedding_model_name (str): The name of the embedding model to use.
            batch_size (int): The size of the batches to use when embedding names. 
            Default 4096
        """
        if (
            embedding_model_name == self.cnf_l.embedding_model_name
            and "cui_embeddings" in self.cdb.addl_info
            and "name_embeddings" in self.cdb.addl_info
        ):
            logger.warning("Using the same model for embedding.")
        else:
            self.cnf_l.embedding_model_name = embedding_model_name

        # Use the longest name
        cui_names = [
            max(self.cdb.cui2info[cui]["names"], key=len) for cui in self._cui_keys
        ]
        # embed each name in batches. Because there can be 3+ million names
        total_batches = math.ceil(len(cui_names) / self.cnf_l.embedding_batch_size)
        all_embeddings = []
        for names in tqdm(
            self._batch_data(cui_names, self.cnf_l.embedding_batch_size),
            total=total_batches,
            desc="Embedding cuis' preferred names",
        ):
            with torch.no_grad():
                # removing ~ from names, as it is used to indicate a space in the CDB
                names_to_embed = [
                    name.replace(self.config.general.separator, " ") for name in names
                ]
                embeddings = self.embed(names_to_embed, self.device)
                all_embeddings.append(embeddings.cpu())
        # cat all batches into one tensor
        all_embeddings_matrix = torch.cat(all_embeddings, dim=0)
        self.cdb.addl_info["cui_embeddings"] = all_embeddings_matrix
        logger.debug("Embedding cui names done, total: %d", len(names))

    def embed_names(self, embedding_model_name: Optional[str] = None) -> None:
        """Obtain embeddings for all names in the CDB using the specified
        embedding model and store them in the name2info.context_vectors
        Args:
            embedding_model_name (str): The name of the embedding model to use.
            batch_size (int): The size of the batches to use when embedding names
            Default 4096
        """
        if embedding_model_name == None or embedding_model_name == self.cnf_l.embedding_model_name:
            logger.debug("Using the same model for embedding names.")
        else:
            self.cnf_l.embedding_model_name = embedding_model_name
        names = self._name_keys
        # embed each name in batches. Because there can be 3+ million names
        total_batches = math.ceil(len(names) / self.cnf_l.embedding_batch_size)
        all_embeddings = []
        for names in tqdm(
            self._batch_data(names, self.cnf_l.embedding_batch_size),
            total=total_batches,
            desc="Embedding names",
        ):
            with torch.no_grad():
                # removing ~ from names, as it is used to indicate a space in the CDB
                names_to_embed = [
                    name.replace(self.config.general.separator, " ") for name in names
                ]
                embeddings = self.embed(names_to_embed, self.device)
                all_embeddings.append(embeddings.cpu())
        all_embeddings_matrix = torch.cat(all_embeddings, dim=0)
        self.cdb.addl_info["name_embeddings"] = all_embeddings_matrix
        logger.debug("Embedding names done, total: %d", len(names))
    
    def embed(self, to_embed: list[str], device) -> Tensor:
        """Embeds a list of strings"""
        batch_dict = self.tokenizer(
            to_embed,
            max_length=self.cnf_l.max_token_length,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(device)
        outputs = self.model(**batch_dict)
        return outputs