from medcat.cdb import CDB
from medcat.config.config import Config, ComponentConfig
from medcat.components.types import CoreComponentType
from medcat_embedding_linker.embedding_linker import Linker
from medcat.tokenizing.tokens import MutableEntity, MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat_embedding_linker.transformer_embedding_model import ContextModel
from medcat.components.linking.vector_context_model import PerDocumentTokenCache
from typing import Optional, Iterator, Set, Union
from medcat.vocab import Vocab
from medcat.utils.postprocessing import filter_linked_annotations
from tqdm import tqdm
from collections import defaultdict
import logging
import math
import numpy as np

from medcat_embedding_linker.config import EmbeddingLinking

from torch import Tensor
from transformers import AutoTokenizer, AutoModel
import torch.nn.functional as F
import torch

logger = logging.getLogger(__name__)


class TrainableEmbeddingLinker(Linker):
    name = "embedding_linker"
    def __init__(self, cdb: CDB, config: Config) -> None:
        """Initializes the embedding linker with a CDB and configuration.
        Args:
            cdb (CDB): The concept database to use.
            config (Config): The base config.
        """
        super().__init__(cdb, config)

        self.embedding_model = ContextModel(
            config.components.linking)
        self.use_projection_layer = self.cnf_l.use_projection_layer
        self.training_batch = []

    def _generate_negative_samples(self, candidate_indices: Tensor, names_scores: Tensor, positive_name_idxs: list[int]) -> list[str]:
        """Generate negative samples for a given entity and its true CUI.
        Args:
            candidate_indices (Tensor): The indices of the candidate CUIs.
            names_scores (Tensor): The scores for each name.
            gold_cui_idx (int): The index of the ground truth CUI.
        Returns:
            list[str]: A list of negative sample CUIs.
        """
        k = self.cnf_l.negative_sampling_k
        temperature = self.cnf_l.negative_sampling_temperature

        # Gather scores for the sorted candidates
        candidate_scores = names_scores[candidate_indices]

        # Temperature scaling
        probs = torch.softmax(candidate_scores / temperature, dim=0)

        # Sample negatives
        sampled_positions = torch.multinomial(
            probs,
            num_samples=min(k, len(candidate_indices)),
            replacement=False
        )

        negative_indices = candidate_indices[sampled_positions]
        return negative_indices

    def _train_on_batch(self, entities: list[MutableEntity], doc: MutableDocument, positive_name_idxs: list[int]) -> None:
        """Train on a batch of entities and their corresponding document.
        Args:
            ents (list[MutableEntity]): The entities to train on.
            doc (MutableDocument): The document the entities were detected in.
        """
        detected_context_vectors = self._get_context_vectors(
            doc, entities, self.cnf_l.context_window_size
        )

        # score all detected contexts vs all names
        names_scores = detected_context_vectors @ self.names_context_matrix.T
        sorted_indices = torch.argsort(names_scores, dim=1, descending=True)

        
        self._generate_negative_samples(sorted_indices, names_scores, positive_name_idxs)


    def train(self, cui: str,
              entity: MutableEntity,
              doc: MutableDocument,
              negative: bool = False,
              names: Union[list[str], dict] = [],
              per_doc_valid_token_cache: Optional[PerDocumentTokenCache] = None
              ) -> None:
        """Train the linker.

        This simply trains the context model.

        This will collect samples to train in batches. Once a batch is ready, the forward
        pass will be done and gradients will be collected.

        Args:
            cui (str): The ground truth label for the entity.
            entity (BaseEntity): The entity we're at.
            doc (BaseDocument): The document within which we're working.
            negative (bool): To be ignored here.
            names (list[str]/dict):
                Unused within the embedding linker, but required for the interface. 
                Can be used to provide the names of the concept for which we're training.
            per_doc_valid_token_cache (PerDocumentTokenCache):
                Unused within the embedding linker, but required for the interface. 
        """
        """TODO: Ignore negative samples. If true throw a warning and skip.
        Pre-process entity training sample.
        Pre-process involves getting negative sampling done.
        Add to batch. If batch is full or last entity of document, train on batch.
        """
        if negative:
            logger.warning(
                "Negative samples are not currently used in training the embedding linker. Skipping."
            )
            return
        # all positive samples are trained on
        positive_samples = self.cdb.cui2info[cui]["names"]
        # atm training on all potential names for CUI, but this could be changed to a sampling approach if there are too many names per CUI
        # as its unbalanced
        # TODO: CHeck performance of sampling vs using all names
        self.training_batch.extend((doc, entity, sample) for sample in positive_samples)
        # if the batch is full, or it is the last entity of the document, train on the batch
        if len(self.training_batch) >= self.cnf_l.training_batch_size or entity == doc.ner_ents[-1]:
            self._train_on_batch(self.training_batch)
            self.training_batch = []
        if self.number_of_batches > self.cnf_l.embed_per_n_batches:
            self.context_model.embed_names()
            self.number_of_batches = 0
        

    @classmethod
    def create_new_component(
        cls,
        cnf: ComponentConfig,
        tokenizer: BaseTokenizer,
        cdb: CDB,
        vocab: Vocab,
        model_load_path: Optional[str],
    ) -> "TrainableEmbeddingLinker":
        return cls(cdb, cdb.config)
