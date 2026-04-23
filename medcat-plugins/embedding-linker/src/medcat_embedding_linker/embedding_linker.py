from medcat.cdb import CDB
from medcat.config.config import Config, ComponentConfig
from medcat.components.types import CoreComponentType
from medcat.components.types import AbstractEntityProvidingComponent
from medcat.tokenizing.tokens import MutableEntity, MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat_embedding_linker.transformer_context_model import ContextModel
from typing import Optional, Iterator, Set, Any
from medcat.vocab import Vocab
from medcat.utils.postprocessing import filter_linked_annotations
from medcat_embedding_linker.config import EmbeddingLinking
from collections import defaultdict
from torch import Tensor
import logging
import numpy as np
import torch

logger = logging.getLogger(__name__)


class Linker(AbstractEntityProvidingComponent):
    name = "embedding_linker"
    _MODEL_FOLDER_NAME = "embedding_model"
    _STATE_FILE_NAME = "state.json"

    # default model kwargs for embedding linkers that do not require training
    DEFAULT_MODEL_INIT_KWARGS = {
        "use_projection_layer": False,
        "top_n_layers_to_unfreeze": 0,
    }

    def __init__(
        self,
        cdb: CDB,
        config: Config,
        model_init_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initializes the embedding linker with a CDB and configuration.
        Args:
            cdb (CDB): The concept database to use.
            config (Config): The base config.
            model_init_kwargs (Optional[dict[str, Any]]): Explicit kwargs that
                override linker defaults.
        """
        super().__init__()
        self.cdb = cdb
        self.config = config
        if not isinstance(config.components.linking, EmbeddingLinking):
            raise TypeError("Linking config must be an EmbeddingLinking instance")
        self.cnf_l: EmbeddingLinking = config.components.linking
        self.max_length: Optional[int] = self.cnf_l.max_token_length
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        resolved_model_init_kwargs: dict[str, Any] = dict(
            self.DEFAULT_MODEL_INIT_KWARGS
        )
        resolved_model_init_kwargs.update(model_init_kwargs or {})

        self.context_model = ContextModel(
            cdb=self.cdb,
            linking_config=self.cnf_l,
            separator=self.config.general.separator,
            model_init_kwargs=resolved_model_init_kwargs,
        )
        # checking for config settings that aren't used in this linker
        if self.cnf_l.prefer_frequent_concepts:
            logger.warning(
                "linker_config.prefer_frequent_concepts is not used "
                "in the embedding linker. It is currently set to "
                f"{self.cnf_l.prefer_frequent_concepts}."
            )

        if self.cnf_l.prefer_primary_name:
            logger.warning(
                "linker_config.prefer_primary_name is not used "
                "in the embedding linker. It is currently set to "
                f"{self.cnf_l.prefer_primary_name}."
            )
        self.refresh_structure()

    def refresh_structure(self) -> None:
        """Call this method after making changes to the CDB to update internal 
        structures. Called upon initialization, and can be called manually after 
        CDB modifications. This is usually required when training on data that 
        might have new cuis or names."""
        self._name_keys = list(self.cdb.name2info)
        self._cui_keys = list(self.cdb.cui2info)

        # Clear context matrices to force re-embedding with new CDB structure
        self._names_context_matrix = None
        self._cui_context_matrix = None

        # used for filters and name embedding, and if the name contains a valid cui
        # see: _set_filters
        self._last_include_set: Optional[Set[str]] = None
        self._last_exclude_set: Optional[Set[str]] = None
        self._allowed_mask = None
        self._name_has_allowed_cui = None

        self._cui_to_idx = {cui: idx for idx, cui in enumerate(self._cui_keys)}
        self._name_to_idx = {name: idx for idx, name in enumerate(self._name_keys)}
        self._name_to_cui_idxs = [
            [
                self._cui_to_idx[cui]
                for cui in self.cdb.name2info[name].get("per_cui_status", {}).keys()
                if cui in self._cui_to_idx
            ]
            for name in self._name_keys
        ]
        self._initialize_filter_structures()

    def create_embeddings(
        self,
        embedding_model_name: Optional[str] = None,
        max_length: Optional[int] = None,
    ) -> None:
        """Create both CUI and name embeddings in CDB."""
        if embedding_model_name is None:
            embedding_model_name = self.cnf_l.embedding_model_name

        if max_length is not None and max_length != self.max_length:
            logger.info(
                "Updating max_length from %s to %s", self.max_length, max_length
            )
            self.max_length = max_length
            self.cnf_l.max_token_length = max_length
            self.context_model.max_length = max_length

        # Route model swaps through linker-level hook so trainable variants can
        # refresh optimizer/scaler when underlying params change.
        self.load_transformers(embedding_model_name)
        self.context_model.embed_cuis()
        self.context_model.embed_names()

        self._names_context_matrix = None
        self._cui_context_matrix = None

    def load_transformers(self, embedding_model_name: str) -> None:
        """Pass through to the underlying transformer model for context embedding."""
        self.context_model.load_transformers(embedding_model_name)

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking

    def _batch_data(self, data, batch_size=512) -> Iterator[list]:
        for i in range(0, len(data), batch_size):
            yield data[i : i + batch_size]

    def _get_context(
        self, entity: MutableEntity, doc: MutableDocument, size: int
    ) -> tuple[str, tuple[int, int]]:
        """Get context tokens for an entity

        Args:
            entity (BaseEntity): The entity to look for.
            doc (BaseDocument): The document look in.
            size (int): The size of the entity.

        Returns:
            tuple[str, tuple[int, int]]:
                The context text and the span of the entity within that text.
        """
        # Token indices of the entity
        start_token_idx = entity.base.start_index
        end_token_idx = entity.base.end_index

        # Define token window
        left_token_idx = max(0, start_token_idx - size)
        right_token_idx = min(len(doc) - 1, end_token_idx + size)

        # Convert tokens → character offsets
        left_most_token = doc[left_token_idx]
        right_most_token = doc[right_token_idx]

        # For mention masking
        snippet_start_char = left_most_token.base.char_index
        snippet_end_char = right_most_token.base.char_index + len(
            right_most_token.base.text
        )

        # Slice raw document text
        snippet = doc.base.text[snippet_start_char:snippet_end_char]

        # Compute entity span relative to snippet
        mention_start = entity.base.start_char_index - snippet_start_char
        mention_end = entity.base.end_char_index - snippet_start_char

        return snippet, (mention_start, mention_end)

    def _get_context_vectors(
        self, doc: MutableDocument, entities: list[MutableEntity], size: int
    ) -> Tensor:
        """Get context vectors for all detected concepts based on their
        surrounding text.

        Args:
            doc (BaseDocument): The document look in.
            size (int): The size of the entity.
        Returns:
            tuple[list[BaseToken], list[BaseToken], list[BaseToken]]:
                The tokens on the left, centre, and right."""
        texts = []
        mention_spans = []
        for entity in entities:
            text, span = self._get_context(entity, doc, size)
            texts.append(text)
            mention_spans.append(span)
        return self.context_model.embed(texts, mention_spans, self.device)

    def _initialize_filter_structures(self) -> None:
        """Call once during initialization to create efficient lookup structures."""
        # Build an inverted index: cui_idx -> list of name indices that contain it
        # This is the KEY optimization - we flip the lookup direction
        cui2name_indices: defaultdict[int, list[int]] = defaultdict(list)

        for name_idx, cui_idxs in enumerate(self._name_to_cui_idxs):
            for cui_idx in cui_idxs:
                cui2name_indices[cui_idx].append(name_idx)

        # Convert lists to numpy arrays for faster indexing
        self._cui_idx_to_name_idxs = {
            cui_idx: np.array(name_idxs, dtype=np.int32)
            for cui_idx, name_idxs in cui2name_indices.items()
        }

        # This used to be checked to be cached.
        # But whenever it is called it is needed.
        self._has_cuis_all_cached = torch.tensor(
            [
                bool(self.cdb.name2info[name]["per_cui_status"])
                for name in self._name_keys
            ],
            device=self.device,
            dtype=torch.bool,
        )

    def _get_include_filters_1cui(self, cui: str, n: int) -> torch.Tensor:
        """Optimized single CUI include filter using inverted index."""
        if cui not in self._cui_to_idx:
            return torch.zeros(n, dtype=torch.bool, device=self.device)

        cui_idx = self._cui_to_idx[cui]

        # Use inverted index: get all name indices that contain this CUI
        if cui_idx in self._cui_idx_to_name_idxs:
            name_indices = self._cui_idx_to_name_idxs[cui_idx]

            # Create mask by setting specific indices to True
            allowed_mask = torch.zeros(n, dtype=torch.bool, device=self.device)
            allowed_mask[torch.from_numpy(name_indices).to(self.device)] = True
            return allowed_mask
        else:
            return torch.zeros(n, dtype=torch.bool, device=self.device)

    def _get_include_filters_multi_cui(
        self, include_set: Set[str], n: int
    ) -> torch.Tensor:
        """Optimized multi-CUI include filter using inverted index."""
        include_cui_idxs = [
            self._cui_to_idx[cui] for cui in include_set if cui in self._cui_to_idx
        ]

        if not include_cui_idxs:
            return torch.zeros(n, dtype=torch.bool, device=self.device)

        # Collect all name indices from inverted index
        all_name_indices_list: list[np.ndarray] = []
        for cui_idx in include_cui_idxs:
            if cui_idx in self._cui_idx_to_name_idxs:
                all_name_indices_list.append(self._cui_idx_to_name_idxs[cui_idx])

        if not all_name_indices_list:
            return torch.zeros(n, dtype=torch.bool, device=self.device)

        # Concatenate and get unique indices
        all_name_indices = np.unique(np.concatenate(all_name_indices_list))

        # Create mask
        allowed_mask = torch.zeros(n, dtype=torch.bool, device=self.device)
        allowed_mask[torch.from_numpy(all_name_indices).to(self.device)] = True
        return allowed_mask

    def _get_include_filters(self, include_set: Set[str], n: int) -> torch.Tensor:
        """Route to appropriate include filter method."""
        if len(include_set) == 1:
            cui = next(iter(include_set))
            return self._get_include_filters_1cui(cui, n)
        else:
            return self._get_include_filters_multi_cui(include_set, n)

    def _get_exclude_filters_1cui(
        self, allowed_mask: torch.Tensor, cui: str
    ) -> torch.Tensor:
        """Optimized single CUI exclude filter using inverted index."""
        if cui not in self._cui_to_idx:
            return allowed_mask

        cui_idx = self._cui_to_idx[cui]

        if cui_idx in self._cui_idx_to_name_idxs:
            name_indices = self._cui_idx_to_name_idxs[cui_idx]
            # Set specific indices to False
            allowed_mask[torch.from_numpy(name_indices).to(self.device)] = False

        return allowed_mask

    def _get_exclude_filters_multi_cui(
        self,
        allowed_mask: torch.Tensor,
        exclude_set: Set[str],
    ) -> torch.Tensor:
        """Optimized multi-CUI exclude filter using inverted index."""
        exclude_cui_idxs = [
            self._cui_to_idx[cui] for cui in exclude_set if cui in self._cui_to_idx
        ]

        if not exclude_cui_idxs:
            return allowed_mask

        # Collect all name indices to exclude
        _all_name_indices: list[np.ndarray] = []
        for cui_idx in exclude_cui_idxs:
            if cui_idx in self._cui_idx_to_name_idxs:
                _all_name_indices.append(self._cui_idx_to_name_idxs[cui_idx])

        if _all_name_indices:
            all_name_indices = np.unique(np.concatenate(_all_name_indices))
            allowed_mask[torch.from_numpy(all_name_indices).to(self.device)] = False

        return allowed_mask

    def _get_exclude_filters(self, exclude_set: Set[str], n: int) -> torch.Tensor:
        """Route to appropriate exclude filter method."""
        # Start with all allowed
        allowed_mask = torch.ones(n, dtype=torch.bool, device=self.device)

        if not exclude_set:
            return allowed_mask

        if len(exclude_set) == 1:
            cui = next(iter(exclude_set))
            return self._get_exclude_filters_1cui(allowed_mask, cui)
        else:
            return self._get_exclude_filters_multi_cui(allowed_mask, exclude_set)

    def _set_filters(self) -> None:
        include_set = self.cnf_l.filters.cuis
        exclude_set = self.cnf_l.filters.cuis_exclude

        # Check if sets changed (avoid recomputation if same)
        if (
            self._last_include_set is not None
            and self._last_exclude_set is not None
            and include_set == self._last_include_set
            and exclude_set == self._last_exclude_set
        ):
            return

        n = len(self._name_keys)

        if include_set:
            allowed_mask = self._get_include_filters(include_set, n)
        else:
            allowed_mask = self._get_exclude_filters(exclude_set, n)

        self._valid_names = self._has_cuis_all_cached & allowed_mask
        self._last_include_set = set(include_set) if include_set is not None else None
        self._last_exclude_set = set(exclude_set) if exclude_set is not None else None

    def _disambiguate_by_cui(
        self, cui_candidates: list[str], scores: Tensor
    ) -> tuple[str, float]:
        """Disambiguate a detected concept by a list of potential cuis
        Args:
            cuis (list[str]): Potential cuis
            cui_to_idx (dict[str, int]): Mapping of cui to relevant idx position
            scores (Tensor): Scores for the detected cui2info concepts similarity
            cui_keys (list[str]): idx_to_cui inverse
        Returns:
            tuple[str, float]:
                The CUI and its similarity
        """
        cui_idxs = [
            self._cui_to_idx[cui] for cui in cui_candidates if cui in self._cui_to_idx
        ]
        candidate_scores = scores[cui_idxs]
        candidate_idx = int(torch.argmax(candidate_scores).item())
        best_idx = cui_idxs[candidate_idx]

        predicted_cui = self._cui_keys[best_idx]
        similarity = float(candidate_scores[candidate_idx].item())
        return predicted_cui, similarity

    def _inference(
        self, doc: MutableDocument, entities: list[MutableEntity]
    ) -> Iterator[MutableEntity]:
        """Infer all entities at once (or in batches), to avoid multiple gpu calls
        when it isn't nessescary.
        Args:
            doc (BaseDocument): The document look in.
            entities (list[BaseEntity]): The entities to infer.
        Yields:
            entity (MutableEntity): Entity with a relevant cui prediction -
            or skip if it's not suitable."""
        detected_context_vectors = self._get_context_vectors(
            doc, entities, self.cnf_l.context_window_size
        )

        # score all detected contexts vs all names
        names_scores = detected_context_vectors @ self.names_context_matrix.T
        cui_scores = detected_context_vectors @ self.cui_context_matrix.T
        sorted_indices = torch.argsort(names_scores, dim=1, descending=True)

        for i, entity in enumerate(entities):
            link_candidates = entity.link_candidates
            if self.config.components.linking.filter_before_disamb:
                link_candidates = [
                    cui
                    for cui in link_candidates
                    if self.cnf_l.filters.check_filters(cui)
                ]
            if len(link_candidates) == 1:
                best_idx = self._cui_to_idx[link_candidates[0]]
                predicted_cui = link_candidates[0]
                if best_idx < 0 or best_idx >= cui_scores.shape[1]:
                    logger.warning(
                        "Skipping entity '%s': single-candidate index %s is out of "
                        "bounds for cui_scores width %s.",
                        entity.detected_name,
                        best_idx,
                        cui_scores.shape[1],
                    )
                    continue
                similarity = cui_scores[i, best_idx].item()
            elif len(link_candidates) > 1:
                name_to_cuis = defaultdict(list)
                for cui in link_candidates:
                    for name in self.cdb.cui2info[cui]["names"]:
                        name_to_cuis[name].append(cui)

                name_idxs = [
                    self._name_to_idx[name]
                    for name in name_to_cuis
                    if name in self._name_to_idx
                ]
                if name_idxs == []:
                    logger.warning(
                        "No valid name indices for entity '%s' link candidates. "
                        "Likely stale linker structure after CDB mutation; call "
                        "refresh_structure() and recreate embeddings.",
                        entity.detected_name,
                    )
                    continue
                indexed_scores = names_scores[i, name_idxs]
                best_local_pos = int(torch.argmax(indexed_scores).item())
                best_global_idx = name_idxs[best_local_pos]
                similarity = names_scores[i, best_global_idx].item()
                best_name = self._name_keys[best_global_idx]
                cuis = name_to_cuis[best_name]
                if len(cuis) == 1:
                    predicted_cui = cuis[0]
                else:
                    predicted_cui, _ = self._disambiguate_by_cui(cuis, cui_scores[i, :])
            else:
                row_sorted = sorted_indices[i]  # sorted candidate indices for entity i

                # Find the first candidate in this row with CUIs
                first_true_pos = int(
                    torch.nonzero(self._valid_names[row_sorted], as_tuple=True)[0][
                        0
                    ].item()
                )

                # Get global index + name
                top_name_idx = int(row_sorted[first_true_pos].item())
                similarity = names_scores[i, top_name_idx].item()
                detected_name = self._name_keys[top_name_idx]
                cuis = list(self.cdb.name2info[detected_name]["per_cui_status"].keys())

                predicted_cui, _ = self._disambiguate_by_cui(cuis, cui_scores[i, :])
            if not self.cnf_l.filters.check_filters(predicted_cui):
                continue
            if self._check_similarity(similarity):
                entity.cui = predicted_cui
                entity.context_similarity = similarity
                yield entity

    def _check_similarity(self, context_similarity: float) -> bool:
        if self.cnf_l.long_similarity_threshold:
            threshold = self.cnf_l.long_similarity_threshold
            return context_similarity >= threshold
        else:
            return True

    def _build_context_matrices(self) -> None:
        if "name_embeddings" in self.cdb.addl_info:
            self._names_context_matrix = (
                self.cdb.addl_info["name_embeddings"].half().to(self.device)
            )
        if "cui_embeddings" in self.cdb.addl_info:
            self._cui_context_matrix = (
                self.cdb.addl_info["cui_embeddings"].half().to(self.device)
            )

    def _generate_link_candidates(
        self, doc: MutableDocument, entities: list[MutableEntity]
    ) -> None:
        """Generate link candidates for each detected entity based
        on context vectors with size 0. Compare to names to get the most
        similar name in the cdb to the detected concept."""
        detected_context_vectors = self._get_context_vectors(doc, entities, 0)

        # score all detected contexts vs all names
        names_scores = detected_context_vectors @ self.names_context_matrix.T
        sorted_indices = torch.argsort(names_scores, dim=1, descending=True)

        for i, entity in enumerate(entities):
            row_sorted = sorted_indices[i]
            cuis: set[str] = set()

            # scores for this entity row
            row_scores = names_scores[i, row_sorted]
            # valid names via filtering and contain at least 1 cui
            valid_mask = self._valid_names[row_sorted]

            if self.cnf_l.short_similarity_threshold > 0:
                # thresholded selection
                above_thresh_mask = row_scores >= self.cnf_l.short_similarity_threshold
                selected_mask = valid_mask & above_thresh_mask
                valid_positions = torch.nonzero(selected_mask, as_tuple=True)[0]
            else:
                # just take the single best valid candidate
                first_valid = torch.nonzero(valid_mask, as_tuple=True)[0][:1]
                valid_positions = first_valid

            for pos in valid_positions.tolist():
                top_name_idx = int(row_sorted[pos].item())
                detected_name = self._name_keys[top_name_idx]
                cuis.update(self.cdb.name2info[detected_name]["per_cui_status"].keys())

            entity.link_candidates = list(cuis)

    def _pre_inference(
        self, doc: MutableDocument
    ) -> tuple[list[MutableEntity], list[MutableEntity]]:
        """Checking all entities for entites with only a single link candidate and to
        avoid full inference step. If we want to calculate similarities, or not use
        link candidates then just return the entities"""
        all_ents = doc.ner_ents
        if not self.cnf_l.use_ner_link_candidates:
            to_generate_link_candidates = all_ents
        else:
            to_generate_link_candidates = [
                entity for entity in all_ents if not entity.link_candidates
            ]

        # generate our own link candidates if it's required, or wanted
        for entities in self._batch_data(
            to_generate_link_candidates, self.cnf_l.linking_batch_size
        ):
            self._generate_link_candidates(doc, entities)

        # filter out entities with no link candidates after thresholding
        filtered_ents = [ent for ent in all_ents if ent.link_candidates]

        if self.cnf_l.always_calculate_similarity:
            return [], filtered_ents

        le: list[MutableEntity] = []
        to_infer: list[MutableEntity] = []
        for entity in all_ents:
            if len(entity.link_candidates) == 1:
                # if the include filter exists and the only cui is in it
                if self.cnf_l.filters.check_filters(entity.link_candidates[0]):
                    entity.cui = entity.link_candidates[0]
                    entity.context_similarity = 1
                    le.append(entity)
                    continue
            elif self.cnf_l.use_ner_link_candidates and not entity.link_candidates:
                continue
            # it has to be inferred due to filters or number of link candidates
            to_infer.append(entity)
        return le, to_infer

    def predict_entities(
        self, doc: MutableDocument, ents: list[MutableEntity] | None = None
    ) -> list[MutableEntity]:
        if self.cnf_l.train and self.comp_name == "embedding_linker":
            logger.warning(
                "Attemping to train a static embedding linker. "
                "This is not possible / required."
                "Use the `trainable_embedding_linker` instead."
            )
        if self.cnf_l.filters.cuis and self.cnf_l.filters.cuis_exclude:
            logger.warning(
                "You have both include and exclude filters for CUIs set. "
                "This will result in only include CUIs being filtered."
            )

        self._set_filters()

        with torch.no_grad():
            le, to_infer = self._pre_inference(doc)
            for entities in self._batch_data(to_infer, self.cnf_l.linking_batch_size):
                le.extend(list(self._inference(doc, entities)))

        return filter_linked_annotations(doc, le)

    @property
    def names_context_matrix(self):
        if self._names_context_matrix is None:
            self._build_context_matrices()
        return self._names_context_matrix

    @property
    def cui_context_matrix(self):
        if self._cui_context_matrix is None:
            self._build_context_matrices()
        return self._cui_context_matrix

    @classmethod
    def create_new_component(
        cls,
        cnf: ComponentConfig,
        tokenizer: BaseTokenizer,
        cdb: CDB,
        vocab: Vocab,
        model_load_path: Optional[str],
    ) -> "Linker":
        return cls(cdb, cdb.config)
