from typing import Optional, Union
from medcat_embedding_linker.config import EmbeddingLinking
from torch import Tensor
from medcat.cdb import CDB
from medcat.config.config import Config, ComponentConfig
from medcat.components.linking.vector_context_model import PerDocumentTokenCache
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.vocab import Vocab
from medcat_embedding_linker.embedding_linker import Linker
from medcat.storage.serialisables import AbstractManualSerialisable
import logging
import torch
import os
import random

logger = logging.getLogger(__name__)


class TrainableEmbeddingLinker(Linker, AbstractManualSerialisable):
    """Trainable variant of the embedding linker.
    This class inherits inference and embedding behavior from Linker and provides
    method hooks for online/offline training.
    """

    comp_name = "trainable_embedding_linker"
    _MODEL_FOLDER_NAME = "trainable_embedding_model"
    _MODEL_STATE_FILE_NAME = "model_state.pt"

    def __init__(self, cdb: CDB, config: Config) -> None:
        if not isinstance(config.components.linking, EmbeddingLinking):
            raise TypeError("Linking config must be an EmbeddingLinking instance")
        self.cnf_l: EmbeddingLinking = config.components.linking
        # these by default are True, and 0
        # so a projection layer is used, but only the projection is trained
        model_init_kwargs = {
            "use_projection_layer": self.cnf_l.use_projection_layer,
            "top_n_layers_to_unfreeze": self.cnf_l.top_n_layers_to_unfreeze,
        }
        super().__init__(
            cdb,
            config,
            model_init_kwargs=model_init_kwargs,
        )
        self.training_batch: list[tuple] = []
        self.number_of_batches = 0
        self.negative_sampling_candidate_pool_size = (
            self.cnf_l.negative_sampling_candidate_pool_size
        )
        self.scaler = torch.amp.GradScaler()  # for FP16 training stability
        self.optimizer = torch.optim.AdamW(
            self.context_model.model.parameters(), lr=1e-4, weight_decay=0.01
        )

    def _generate_negative_samples(
        self,
        candidate_indices: Tensor,
        candidate_scores: Tensor,
        positive_target_idxs_per_row: list[list[int]],
    ) -> Tensor:
        """Sample negative target indices for each entity in a batch.

        Args:
            candidate_indices (Tensor): Candidate target indices, shape
                ``[batch, num_candidates]``.
            candidate_scores (Tensor): Scores for candidate targets aligned with
                ``candidate_indices``, shape ``[batch, num_candidates]``.
            positive_target_idxs_per_row (list[list[int]]): Per-row target indices that
                must be excluded from negatives.

        Returns:
            Tensor: Sampled negative name indices with shape ``[batch, k]`` (or
            ``[k]`` for single-item input).
        """
        k = self.cnf_l.negative_sampling_k
        temperature = self.cnf_l.negative_sampling_temperature

        # Exclude positives from sampling by masking their scores.
        positive_mask = torch.zeros_like(candidate_indices, dtype=torch.bool)
        for row_idx, row_positive_idxs in enumerate(positive_target_idxs_per_row):
            if not row_positive_idxs:
                continue
            row_positive_tensor = torch.tensor(
                row_positive_idxs,
                device=candidate_indices.device,
                dtype=candidate_indices.dtype,
            )
            positive_mask[row_idx] = torch.isin(
                candidate_indices[row_idx],
                row_positive_tensor,
            )
        candidate_scores = candidate_scores.masked_fill(positive_mask, float("-inf"))

        probs = torch.softmax(candidate_scores / temperature, dim=1)
        probs = torch.nan_to_num(probs, nan=0.0, posinf=0.0, neginf=0.0)

        max_samples = min(k, candidate_indices.size(1))
        valid_counts = (~positive_mask).sum(dim=1)
        sample_count = min(max_samples, int(valid_counts.min().item()))
        if sample_count <= 0:
            return candidate_indices.new_empty((candidate_indices.size(0), 0))

        sampled_positions = torch.multinomial(
            probs,
            num_samples=sample_count,
            replacement=False,
        )
        negative_indices = torch.gather(
            candidate_indices, dim=1, index=sampled_positions
        )
        return negative_indices

    def _build_batch_context_inputs(
        self, batch: list[tuple]
    ) -> tuple[list[str], list[tuple[int, int]]]:
        """Convert a batch into model-ready text snippets and mention spans."""
        texts: list[str] = []
        mention_spans: list[tuple[int, int]] = []
        for doc, entity, *_ in batch:
            snippet, mention_span = self._get_context(
                entity,
                doc,
                self.cnf_l.context_window_size,
            )
            texts.append(snippet)
            mention_spans.append(mention_span)
        return texts, mention_spans

    def _train_on_batch_targets(
        self,
        target_matrix: Tensor,
        positive_target_idxs: list[int],
        all_positive_target_idxs_per_row: list[list[int]],
    ) -> None:
        """Shared contrastive training path for both name and CUI targets."""
        if self.training_batch == []:
            return

        texts, mention_spans = self._build_batch_context_inputs(self.training_batch)

        self.optimizer.zero_grad()
        with torch.amp.autocast(
            device_type=str(self.device)
        ):  # controls FP16 usage for better stability
            # Forward pass to get context vectors for each entity in the batch.
            self.context_model.model.train()

            context_vectors = self.context_model.embed(
                texts,
                mention_spans=mention_spans,
            )  # [batch, dim]

            # Target embeddings are fixed; no gradient flows through them.
            target_matrix = target_matrix.detach()  # [num_targets, dim]

            # Negative sampling does not need gradients.
            with torch.no_grad():
                target_scores = context_vectors.detach() @ target_matrix.T
                candidate_pool_size = min(
                    target_scores.size(1), self.negative_sampling_candidate_pool_size
                )

                candidate_scores, candidate_indices = torch.topk(
                    target_scores,
                    k=candidate_pool_size,
                    dim=1,
                    largest=True,
                    sorted=False,
                )
                negative_indices = self._generate_negative_samples(
                    candidate_indices,
                    candidate_scores,
                    all_positive_target_idxs_per_row,
                )

            pos_idx_tensor = torch.tensor(positive_target_idxs, device=self.device)
            positive_embeds = target_matrix[pos_idx_tensor]
            negative_embeds = target_matrix[negative_indices]

            positive_scores = (context_vectors * positive_embeds).sum(
                dim=1, keepdim=True
            )
            negative_scores = torch.bmm(
                negative_embeds, context_vectors.unsqueeze(-1)
            ).squeeze(-1)

            logits = torch.cat([positive_scores, negative_scores], dim=1)
            # The target is always the first position (the positive sample).
            # So these are idx's of 0 in the logits tensor, not target indices.
            targets = torch.zeros(
                len(self.training_batch), dtype=torch.long, device=self.device
            )

            loss = torch.nn.functional.cross_entropy(logits, targets)

            self.scaler.scale(loss).backward()
            self.scaler.step(self.optimizer)
            self.scaler.update()

        self.context_model.model.eval()
        logger.debug("Training batch loss: %.4f", loss.item())

    def _train_on_batch_cuis(self) -> None:
        """Train on a batch of CUI-based tuples.

        Runs a contrastive forward pass through the context encoder, computes
        cross-entropy loss over one positive and k negative CUI embeddings, and
        performs a single optimizer step.
        """
        if self.training_batch == []:
            return

        positive_cui_idxs = [sample[2] for sample in self.training_batch]
        if len(self.training_batch[0]) >= 4:
            all_positive_cui_idxs_per_row = [
                sample[3] for sample in self.training_batch
            ]
        else:
            all_positive_cui_idxs_per_row = [[pos_idx] for pos_idx in positive_cui_idxs]

        self._train_on_batch_targets(
            self.cui_context_matrix,
            positive_cui_idxs,
            all_positive_cui_idxs_per_row,
        )

    def _train_on_batch_names(self) -> None:
        """Train on a batch of 
        (doc, entity, positive_name_idx, all_positive_name_idxs) tuples."""
        if self.training_batch == []:
            return

        positive_name_idxs = [sample[2] for sample in self.training_batch]
        all_positive_name_idxs_per_row = [sample[3] for sample in self.training_batch]

        self._train_on_batch_targets(
            self.names_context_matrix,
            positive_name_idxs,
            all_positive_name_idxs_per_row,
        )

    def _train_on_batch(self) -> None:
        """Train on the current batch, dispatching to names or CUI mode.

        This should also be called manually at the end of training to flush any 
        remaining samples that didn't fill a batch.

        Args:
            training_batch (list[tuple]):
                Name mode: (doc, entity, positive_name_idx, all_positive_name_idxs)
                CUI mode: (doc, entity, positive_cui_idx)
        """
        if self.training_batch == []:
            return

        tuple_lengths = {len(sample) for sample in self.training_batch}
        if len(tuple_lengths) != 1:
            raise ValueError(
                "Mixed training batch formats detected. "
                "Expected uniform tuples for names (len=4) or CUIs (len=3)."
            )

        sample_len = tuple_lengths.pop()
        if sample_len == 4:
            # A len=4 tuple is interpreted as name mode by default.
            self._train_on_batch_names()
            return
        if sample_len == 3:
            self._train_on_batch_cuis()
            return

        raise ValueError(
            f"Unsupported training batch tuple size: {sample_len}. "
            "Expected len=3 for CUIs or len=4 for names."
        )

    def train(
        self,
        cui: str,
        entity: MutableEntity,
        doc: MutableDocument,
        negative: bool = False,
        names: Union[list[str], dict] = [],
        per_doc_valid_token_cache: Optional[PerDocumentTokenCache] = None,
    ) -> None:
        """Train the linker.

        This simply trains the context model.

        This will collect samples to train in batches. Once a batch is ready, the 
        forward pass will be done and gradients will be collected.

        Args:
            cui (str): The ground truth label for the entity.
            entity (BaseEntity): The entity we're at.
            doc (BaseDocument): The document within which we're working.
            negative (bool): To be ignored here.
            names (list[str]/dict):
                Unused within the embedding linker, but required for the interface.
                Used to provide the names of the concept for which we're training.
            per_doc_valid_token_cache (PerDocumentTokenCache):
                Unused within the embedding linker, but required for the interface.
        """
        if negative:
            logger.warning(
                "Negative samples are not currently used in training the " \
                "embedding linker. Skipping."
            )
            return
        if self.cnf_l.train_on_names:
            # Name mode: sample one positive name and keep all positive aliases
            # for this CUI so aliases can be excluded from negatives.
            positive_samples = self.cdb.cui2info[cui]["names"]
            all_positive_name_idxs: list[int] = []
            for pos_sample in positive_samples:
                pos_idx = self._name_to_idx.get(pos_sample)
                if pos_idx is not None:
                    all_positive_name_idxs.append(pos_idx)
            if not all_positive_name_idxs:
                return
            pos_idx = random.choice(all_positive_name_idxs)
            self.training_batch.append((doc, entity, pos_idx, all_positive_name_idxs))
        else:
            # CUI mode: one positive CUI index per row.
            positive_cui_idx = self._cui_to_idx.get(cui)
            if positive_cui_idx is None:
                return
            self.training_batch.append((doc, entity, positive_cui_idx))
        if (
            len(self.training_batch) >= self.cnf_l.training_batch_size 
            or entity is doc.linked_ents[-1]
        ):
            logger.debug(
                "End of document reached or full batch; " \
                "training on a batch of size %s",
                len(self.training_batch),
            )
            self._train_on_batch()
            self.training_batch = []
            self.number_of_batches += 1
        # If you've got as many batches as you want before re-embedding, 
        # then do it and reset the counter.
        if (
            self.cnf_l.embed_per_n_batches > 0
            and self.number_of_batches > self.cnf_l.embed_per_n_batches
        ):
            logger.debug(
                "Re-embedding names and CUIs after training on %s batches.",
                self.number_of_batches,
            )
            self.refresh_structure()
            # Always refresh both embeddings to keep CDB and embeddings in sync.
            # Inference always uses both names_context_matrix and cui_context_matrix.
            # And inference is called during the cat.trainer.train() loop
            self.context_model.embed_names()
            self.context_model.embed_cuis()
            self._names_context_matrix = None
            self._cui_context_matrix = None
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

    def serialise_to(self, folder_path: str) -> None:
        os.makedirs(folder_path, exist_ok=True)
        model_folder = os.path.join(folder_path, self._MODEL_FOLDER_NAME)
        os.makedirs(model_folder, exist_ok=True)

        torch.save(
            self.context_model.model.state_dict(),
            os.path.join(model_folder, self._MODEL_STATE_FILE_NAME),
        )

    @classmethod
    def deserialise_from(
        cls, folder_path: str, **init_kwargs
    ) -> "TrainableEmbeddingLinker":
        cdb = init_kwargs["cdb"]
        linker = cls(cdb, cdb.config)

        model_state_path = os.path.join(
            folder_path, cls._MODEL_FOLDER_NAME, cls._MODEL_STATE_FILE_NAME
        )
        if os.path.exists(model_state_path):
            state_dict = torch.load(model_state_path, map_location=linker.device)
            linker.context_model.model.load_state_dict(state_dict)

        linker._names_context_matrix = None
        linker._cui_context_matrix = None
        return linker
