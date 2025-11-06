from medcat.cdb import CDB
from medcat.config.config import Config, ComponentConfig, EmbeddingLinking
from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.tokenizing.tokens import MutableEntity, MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from typing import Optional, Iterator, Set
from medcat.vocab import Vocab
from medcat.utils.postprocessing import create_main_ann
from tqdm import tqdm
from collections import defaultdict
import logging
import math

from medcat.utils.import_utils import ensure_optional_extras_installed
import medcat

# NOTE: the below needs to be before torch/transformers imports
_EXTRA_NAME = "embed-linker"
ensure_optional_extras_installed(medcat.__name__, _EXTRA_NAME)

# avoid linting issues due to above check
from torch import Tensor  # noqa: E402
from transformers import AutoTokenizer, AutoModel  # noqa: E402
import torch.nn.functional as F  # noqa: E402
import torch  # noqa: E402

logger = logging.getLogger(__name__)


class Linker(AbstractCoreComponent):
    name = "embedding_linker"

    def __init__(self, cdb: CDB, config: Config) -> None:
        """Initializes the embedding linker with a CDB and configuration.
        Args:
            cdb (CDB): The concept database to use.
            config (Config): The base config.
        """
        self.cdb = cdb
        self.config = config
        if not isinstance(config.components.linking, EmbeddingLinking):
            raise TypeError("Linking config must be an EmbeddingLinking instance")
        self.cnf_l: EmbeddingLinking = config.components.linking
        self.max_length = self.cnf_l.max_token_length
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self._name_keys = list(self.cdb.name2info)
        self._cui_keys = list(self.cdb.cui2info)

        # these only need to be populated when called for embedding or inference
        self._names_context_matrix = None
        self._cui_context_matrix = None

        # used for filters and name embedding, and if the name contains a valid cui 
        # see: _set_filters
        self._last_include_set: Optional[Set[str]] = None
        self._last_exclude_set: Optional[Set[str]] = None
        self._allowed_mask = None
        self._name_has_allowed_cui = None

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

    def create_embeddings(self, 
                          embedding_model_name: Optional[str] = None,
                          max_length: Optional[int] = None,
                          ):
        """Create embeddings for all names and cuis longest names in the CDB 
        using the chosen embedding model."""
        if embedding_model_name is None:
            embedding_model_name = self.cnf_l.embedding_model_name  # fallback
            
        if max_length is not None and max_length != self.max_length:
            logger.info(
            "Updating max_length from %s to %s", self.max_length, max_length
            )
            self.max_length = max_length
            self.cnf_l.max_token_length = max_length
        if (
            embedding_model_name == self.cnf_l.embedding_model_name
            and "cui_embeddings" in self.cdb.addl_info
        ):
            logger.warning("Using the same model for embedding names.")
        else:
            self.cnf_l.embedding_model_name = embedding_model_name
        self._load_transformers(embedding_model_name)
        self._embed_cui_names(embedding_model_name)
        self._embed_names(embedding_model_name)

    def _embed_cui_names(
        self,
        embedding_model_name: str,
    ) -> None:
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
                embeddings = self._embed(names_to_embed, self.device)
                all_embeddings.append(embeddings.cpu())
        # cat all batches into one tensor
        all_embeddings_matrix = torch.cat(all_embeddings, dim=0)
        self.cdb.addl_info["cui_embeddings"] = all_embeddings_matrix
        logger.debug("Embedding cui names done, total: %d", len(names))

    def _embed_names(self, embedding_model_name: str) -> None:
        """Obtain embeddings for all names in the CDB using the specified
        embedding model and store them in the name2info.context_vectors
        Args:
            embedding_model_name (str): The name of the embedding model to use.
            batch_size (int): The size of the batches to use when embedding names
            Default 4096
        """
        if embedding_model_name == self.cnf_l.embedding_model_name:
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
                embeddings = self._embed(names_to_embed, self.device)
                all_embeddings.append(embeddings.cpu())
        all_embeddings_matrix = torch.cat(all_embeddings, dim=0)
        self.cdb.addl_info["name_embeddings"] = all_embeddings_matrix
        logger.debug("Embedding names done, total: %d", len(names))

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking

    def _batch_data(self, data, batch_size=512) -> Iterator[list]:
        for i in range(0, len(data), batch_size):
            yield data[i : i + batch_size]

    def _load_transformers(self, embedding_model_name: str) -> None:
        """Load the transformers model and tokenizer.
        No need to load a transformer model until it's required.
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
            self.tokenizer = AutoTokenizer.from_pretrained(embedding_model_name)
            self.model = AutoModel.from_pretrained(embedding_model_name)
            self.model.eval()
            gpu_device = self.cnf_l.gpu_device
            self.device = torch.device(
                gpu_device or ("cuda" if torch.cuda.is_available() else "cpu")
            )
            self.model.to(self.device)
            logger.debug(
                f"""Loaded embedding model: {embedding_model_name} 
                on device: {self.device}"""
            )

    def _embed(self, to_embed: list[str], device) -> Tensor:
        """Embeds a list of strings"""
        batch_dict = self.tokenizer(
            to_embed,
            max_length=self.max_length,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(device)
        outputs = self.model(**batch_dict)
        outputs = self._last_token_pool(
            outputs.last_hidden_state, batch_dict["attention_mask"]
        )
        outputs = F.normalize(outputs, p=2, dim=1)
        return outputs.half()

    def _get_context(
        self, entity: MutableEntity, doc: MutableDocument, size: int
    ) -> str:
        """Get context tokens for an entity

        Args:
            entity (BaseEntity): The entity to look for.
            doc (BaseDocument): The document look in.
            size (int): The size of the entity.

        Returns:
            tuple[list[BaseToken], list[BaseToken], list[BaseToken]]:
                The tokens on the left, centre, and right.
        """
        start_ind = entity.base.start_index
        end_ind = entity.base.end_index

        left_most_token = doc[max(0, start_ind - size)]
        left_index = left_most_token.base.char_index

        right_most_token = doc[min(len(doc) - 1, end_ind + size)]
        right_index = right_most_token.base.char_index + len(right_most_token.base.text)

        snippet = doc.base.text[left_index:right_index]
        return snippet

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
        for entity in entities:
            text = self._get_context(entity, doc, size)
            texts.append(text)
        return self._embed(texts, self.device)

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
        allowed_mask = torch.empty(n, dtype=torch.bool, device=self.device)

        if include_set:
            # if in include set, ignore exclude set.
            allowed_mask[:] = False
            include_cui_idxs = {
                self._cui_to_idx[cui] for cui in include_set if cui in self._cui_to_idx
            }
            include_idxs = [
                name_idx
                for name_idx, name_cui_idxs in enumerate(self._name_to_cui_idxs)
                if any(cui in include_cui_idxs for cui in name_cui_idxs)
            ]
            allowed_mask[
                torch.tensor(include_idxs, dtype=torch.long, device=self.device)
            ] = True
        else:
            # only look at exclude if there's no include set
            allowed_mask[:] = True
            if exclude_set:
                exclude_cui_idxs = {
                    self._cui_to_idx[cui]
                    for cui in exclude_set
                    if cui in self._cui_to_idx
                }
                exclude_idxs = [
                    i
                    for i, name_cui_idxs in enumerate(self._name_to_cui_idxs)
                    if any(ci in exclude_cui_idxs for ci in name_cui_idxs)
                ]
                allowed_mask[
                    torch.tensor(exclude_idxs, dtype=torch.long, device=self.device)
                ] = False

        # checking if a name has at least 1 cui related to it.
        _has_cuis_all = torch.tensor(
            [
                bool(self.cdb.name2info[name]["per_cui_status"])
                for name in self._name_keys
            ],
            device=self.device,
            dtype=torch.bool,
        )
        self._valid_names = _has_cuis_all & allowed_mask
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
        cui_idxs = [self._cui_to_idx[cui] for cui in cui_candidates]
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
                similarity = names_scores[i, best_idx].item()
            elif len(link_candidates) > 1:
                name_to_cuis = defaultdict(list)
                for cui in link_candidates:
                    for name in self.cdb.cui2info[cui]["names"]:
                        name_to_cuis[name].append(cui)

                name_idxs = [self._name_to_idx[name] for name in name_to_cuis]
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
            if self._check_similarity(
                similarity
            ):
                entity.cui = predicted_cui
                entity.context_similarity = similarity
                yield entity

    def _check_similarity(self, context_similarity: float) -> bool:
        if self.cnf_l.long_similarity_threshold:
            threshold = self.cnf_l.long_similarity_threshold
            return context_similarity >= threshold
        else:
            return True

    def _last_token_pool(
        self, last_hidden_states: Tensor, attention_mask: Tensor
    ) -> Tensor:
        left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
        if left_padding:
            return last_hidden_states[:, -1]
        else:
            sequence_lengths = attention_mask.sum(dim=1) - 1
            batch_size = last_hidden_states.shape[0]
            return last_hidden_states[
                torch.arange(batch_size, device=last_hidden_states.device),
                sequence_lengths,
            ]

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

    def _pre_inference(self, doc: MutableDocument) -> tuple[list, list]:
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

        le = []
        to_infer = []
        for entity in all_ents:
            if len(entity.link_candidates) == 1:
                # if the include filter exists and the only cui is in it
                if self.cnf_l.filters.check_filters(entity.link_candidates[0]):
                    entity.cui = entity.link_candidates[0]
                    entity.context_similarity = 1
                    le.append(entity)
                    continue
            elif self.cnf_l.use_ner_link_candidates:
                continue
            # it has to be inferred due to filters or number of link candidates
            to_infer.append(entity)
        return le, to_infer

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        # Reset main entities, will be recreated later
        doc.linked_ents.clear()

        if self.cdb.is_dirty:
            logging.warning(
                "CDB has been modified since last save/load. "
                "This might significantly affect linking performance."
            )
            logging.warning(
                "If you have added new concepts or changes, "
                "please re-embed the CDB names and cuis before linking."
            )

        self._load_transformers(self.cnf_l.embedding_model_name)
        if self.cnf_l.train:
            logger.warning(
                "Attemping to train an embedding linker. This is not required."
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

        doc.ner_ents.clear()
        doc.ner_ents.extend(le)
        create_main_ann(doc)

        return doc

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
