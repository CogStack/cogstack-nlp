from medcat.cdb import CDB
from medcat.config.config import Config, ComponentConfig, EmbeddingLinking
from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.tokenizing.tokens import MutableEntity, MutableDocument, MutableToken
from medcat.tokenizing.tokenizers import BaseTokenizer
from typing import Optional, Iterator, cast, Iterable
from medcat.vocab import Vocab
from torch import Tensor
from transformers import AutoTokenizer, AutoModel
from medcat.utils.postprocessing import create_main_ann
from tqdm import tqdm
from collections import defaultdict
import torch.nn.functional as F
import torch
import logging
import math 
logger = logging.getLogger(__name__)

class Linker(AbstractCoreComponent):
    name = "embedding_linker"

    def __init__(self, 
                 cdb: CDB, 
                 config: Config) -> None:
        """Initializes the embedding linker with a CDB and configuration.
        Args:
            cdb (CDB): The concept database to use.
            config (Config): The base config.
            embedding_model_name (Optional[str]): The name of the embedding model to use. Default is "sentence-transformers/all-MiniLM-L6-v2"
            max_length (int): The maximum length of the input sequences for the embedding model. Default is 64.
        """
        self.cdb = cdb
        self.config = config
        if not isinstance(config.components.linking, EmbeddingLinking):
            raise TypeError("Linking config must be an EmbeddingLinking instance")
        self.cnf_l: EmbeddingLinking = config.components.linking
        self.max_length =  self.cnf_l.max_token_length
        self.embedding_model_name = self.cnf_l.embedding_model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # these only need to be populated when called for embedding or inference
        self._name_keys = None
        self._cui_keys = None
        self._names_context_matrix = None
        self._cui_context_matrix = None

        # used for filters, and if the name contains a valid cui see: _set_filters
        self._last_include_set = None
        self._last_exclude_set = None
        self._allowed_mask = None
        self._name_has_allowed_cui = None

        self._cui_to_idx = {cui: idx for idx, cui in enumerate(self.cui_keys)}
        self._name_to_idx = {name: idx for idx, name in enumerate(self.name_keys)}
        self._name_to_cui_idxs = [
            [ self._cui_to_idx[cui]
            for cui in self.cdb.name2info[name].get("per_cui_status", {}).keys()
            if cui in self._cui_to_idx ]
            for name in self._name_keys
        ]

    def embed_cui_names(self, 
                        embedding_model_name: str, 
                        ) -> None:
        """Obtain embeddings for all prefered_names in the CDB using the specified
        embedding model and store them in the name2info.context_vectors
        Args:
            embedding_model_name (str): The name of the embedding model to use.
            batch_size (int): The size of the batches to use when embedding names. Default 4096
        """
        if embedding_model_name == self.embedding_model_name and "cui_embeddings" in self.cdb.addl_info:
            logger.warning("Using the same model for embedding names.")
        else:
            self.embedding_model_name = embedding_model_name
        self._load_transformers(embedding_model_name)
        # use the preferred name, if not take the longest name
        # cui_names = [self.cdb.cui2info[cui]["preferred_name"] for cui in self._name_keys]
        cui_names = [max(self.cdb.cui2info[cui]["names"], key=len) for cui in self._cui_keys]
        # embed each name in batches. Because there can be 3+ million names
        total_batches = math.ceil(len(cui_names) / self.cnf_l.embedding_batch_size)
        all_embeddings = []
        for names in tqdm(self._batch_data(cui_names, self.cnf_l.embedding_batch_size), total=total_batches, desc="Embedding cuis' preferred names"):
            with torch.no_grad():
                # removing ~ from names, as it is used to indicate a space in the CDB
                names_to_embed = [name.replace("~", " ") for name in names]
                embeddings= self._embed(names_to_embed, self.device)
                all_embeddings.append(embeddings.cpu())
        # cat all batches into one tensor
        all_embeddings = torch.cat(all_embeddings, dim=0)
        self.cdb.addl_info["cui_embeddings"] = all_embeddings
        self.cdb.addl_info["cui_to_idx"] = {cui: idx for idx, cui in enumerate(self._cui_keys)}
        logger.debug("Embedding cui names done, total: %d", len(names))

    def embed_names(self, 
                    embedding_model_name: str) -> None:
        """Obtain embeddings for all names in the CDB using the specified
        embedding model and store them in the name2info.context_vectors
        Args:
            embedding_model_name (str): The name of the embedding model to use.
            batch_size (int): The size of the batches to use when embedding names. Default 4096
        """
        if embedding_model_name == self.embedding_model_name:
            logger.debug("Using the same model for embedding names.")
        else:
            self.embedding_model_name = embedding_model_name
        self._load_transformers(embedding_model_name)
        names = list(self.cdb.name2info.keys())
        # embed each name in batches. Because there can be 3+ million names
        total_batches = math.ceil(len(names) / self.cnf_l.embedding_batch_size)
        all_embeddings = []
        for names in tqdm(self._batch_data(names, self.cnf_l.embedding_batch_size), total=total_batches, desc="Embedding names"):
            with torch.no_grad():
                # removing ~ from names, as it is used to indicate a space in the CDB
                names_to_embed = [name.replace("~", " ") for name in names]
                embeddings = self._embed(names_to_embed, self.device)
                all_embeddings.append(embeddings.cpu())
        all_embeddings = torch.cat(all_embeddings, dim=0)
        self.cdb.addl_info["name_embeddings"] = all_embeddings
        self.cdb.addl_info["name_to_idx"] = {name: idx for idx, name in enumerate(self.name_keys)}
        logger.debug("Embedding names done, total: %d", len(names))
    

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking
    
    def _batch_data(self, data, batch_size=512) -> Iterator[list]:
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]

    def _load_transformers(self, 
                           embedding_model_name) -> None:
        """Load the transformers model and tokenizer.
        No need to load a transformer model until it's required.
        Args:
            embedding_model_name (str): The name of the embedding model to load. Default is "sentence-transformers/all-MiniLM-L6-v2"
        """
        if not hasattr(self, "model") or not hasattr(self, "tokenizer") or embedding_model_name != self.cnf_l.embedding_model_name:
            self.cnf_l.embedding_model_name = embedding_model_name
            self.tokenizer = AutoTokenizer.from_pretrained(embedding_model_name)
            self.model = AutoModel.from_pretrained(embedding_model_name)
            self.model.eval()
            gpu_device = self.cnf_l.gpu_device
            self.device = torch.device(gpu_device or ("cuda" if torch.cuda.is_available() else "cpu"))
            self.model.to(self.device)
            logger.debug(f"Loaded embedding model: {embedding_model_name} on device: {self.device}")
    
    def _embed(self,
               to_embed: list[str],
               device) -> Tensor:
        """Embeds a list of strings
        """
        batch_dict = self.tokenizer(to_embed, max_length=self.max_length, padding=True, truncation=True, return_tensors='pt').to(device)
        outputs = self.model(**batch_dict)
        outputs = self._last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
        outputs = F.normalize(outputs, p=2, dim=1)
        return outputs.half()

    def _get_context_tokens(self, 
                            entity: MutableEntity, 
                            doc: MutableDocument,
                            size: int
                           ) -> tuple[list[MutableToken],
                                      list[MutableToken],
                                      list[MutableToken]]:
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

        _left_tokens = doc[max(0, start_ind - size):start_ind]
        tokens_left = [tkn for tkn in _left_tokens]
        tokens_center: list[MutableToken] = list(
            cast(Iterable[MutableToken], entity))
        _right_tokens = doc[end_ind + 1:end_ind + 1 + size]
        tokens_right = [tkn for tkn in _right_tokens]
        
        return tokens_left, tokens_center, tokens_right

    def _get_context_vectors(self,
                             doc: MutableDocument,
                             entities: list[MutableEntity],
                             size: int) -> Tensor:
        """Get context vectors for all detected concepts based on their raw text or detected names.

        Args:
            doc (BaseDocument): The document look in.
            size (int): The size of the entity.
        Returns:
            tuple[list[BaseToken], list[BaseToken], list[BaseToken]]:
                The tokens on the left, centre, and right."""
        texts = []
        for entity in entities:
            tokens_left, tokens_center, tokens_right = self._get_context_tokens(entity, doc, size)
            tokens = tokens_left + tokens_center + tokens_right
            text = " ".join(token.base.text for token in tokens)
            texts.append(text)
        return self._embed(texts, self.device)
    
    def _set_filters(self) -> None:
        include_set = self.cnf_l.filters.cuis
        exclude_set = self.cnf_l.filters.cuis_exclude

        # Check if sets changed (avoid recomputation if same)
        if (include_set == self._last_include_set and
        exclude_set == self._last_exclude_set):
            return 

        n = len(self._name_keys)
        allowed_mask = torch.empty(n, dtype=torch.bool, device=self.device)

        if include_set:
            # if in include set, ignore exclude set.
            allowed_mask[:] = False
            include_cui_idxs = {self._cui_to_idx[cui] for cui in include_set if cui in self._cui_to_idx}
            include_idxs = [
                name_idx
                for name_idx, name_cui_idxs in enumerate(self._name_to_cui_idxs)
                if any(cui in include_cui_idxs for cui in name_cui_idxs)
            ]
            allowed_mask[torch.tensor(include_idxs, dtype=torch.long, device=self.device)] = True
        else:
            # only look at exclude if there's no include set
            allowed_mask[:] = True
            if exclude_set:
                exclude_cui_idxs = {self._cui_to_idx[cui] for cui in exclude_set if cui in self._cui_to_idx}
                exclude_idxs = [i for i, name_cui_idxs in enumerate(self._name_to_cui_idxs) if any(ci in exclude_cui_idxs for ci in name_cui_idxs)]
                allowed_mask[torch.tensor(exclude_idxs, dtype=torch.long, device=self.device)] = False

        # checking if a name has at least 1 cui related to it. Might as well do this cheeck here.
        _has_cuis_all = torch.tensor(
            [bool(self.cdb.name2info[name]["per_cui_status"]) for name in self.name_keys],
            device=self.device
        )
        self._valid_names  = (_has_cuis_all & allowed_mask)
        self._last_include_set = include_set
        self._last_exclude_set = exclude_set

    def _disambiguate_by_cui(self,
                             cui_candidates: list[str],
                             scores: Tensor):
        """Disambiguate a detected concept by a list of potential cuis
        Args:
            cuis (list[str]): Potential cuis
            cui_to_idx (dict[str, int]): Mapping of cui to relevant idx position
            scores (Tensor): Scores for the detected cui2info concepts similarity
            cui_keys (list[str]): idx_to_cui inverse
        Returns:
            tuple[str, int]:
                The CUI and its similarity
        """
        cui_idxs = [self._cui_to_idx[cui] for cui in cui_candidates]
        candidate_scores = scores[cui_idxs]
        candidate_idx = torch.argmax(candidate_scores).item()
        best_idx = cui_idxs[candidate_idx]

        predicted_cui = self._cui_keys[best_idx]
        similarity = candidate_scores[candidate_idx].item()
        return predicted_cui, similarity

    def _inference_by_names(
            self, 
            doc: MutableDocument,
            entities: list[MutableEntity]) -> Iterator[MutableEntity]:
        """Infer all entities at once (or in batches), to avoid multiple gpu calls when it isn't nessescary.
        Args:
            doc (BaseDocument): The document look in.
            name_keys (list[str]): list of all names2info
            cui_keys (list[str]): list of all cuis2info
            context_matrix: Tensor of context matrix we're planning to use could be all names from name2info,
            or prefered names from cui2info[cui]["preferred_name"]
        Yields:
            entity (MutableEntity): Entity with a relevant cui prediction - or skip if it's not suitable."""
        detected_context_vectors = self._get_context_vectors(doc, entities, self.cnf_l.context_window_size)

        # score all detected contexts vs all names, handle in the loop each individual case
        names_scores = detected_context_vectors @ self.names_context_matrix.T
        cui_scores = detected_context_vectors @ self.cui_context_matrix.T
        sorted_indices = torch.argsort(names_scores, dim=1, descending=True)

        for i, entity in enumerate(entities):
            link_candidates = [cui for cui in entity.link_candidates if self.cnf_l.filters.check_filters(cui)]
            if self.cnf_l.use_ner_link_candidates and len(link_candidates) == 1:
                best_idx = self._cui_to_idx[link_candidates[0]]
                predicted_cui = link_candidates[0]
                similarity = names_scores[i, best_idx].item()
            elif self.cnf_l.use_ner_link_candidates and len(link_candidates) > 1:
                name_to_cuis = defaultdict(list)
                for cui in link_candidates:
                    for name in self.cdb.cui2info[cui]["names"]:
                        name_to_cuis[name].append(cui)

                name_idxs = [self._name_to_idx[name] for name in name_to_cuis]
                indexed_scores = names_scores[i, name_idxs]

                best_local_pos = torch.argmax(indexed_scores).item()
                best_global_idx = name_idxs[best_local_pos]
                similarity = names_scores[i, best_global_idx].item()
                best_name = self.name_keys[best_global_idx]
                best_cuis = name_to_cuis[best_name]
                if (len(best_cuis) ==  1):
                    predicted_cui = best_cuis[0]
                else:
                    predicted_cui, _ = self._disambiguate_by_cui(
                        best_cuis,
                        cui_scores[i,:]
                    )
            else:
                row_sorted = sorted_indices[i]  # sorted candidate indices for entity i

                # Find the first candidate in this row with CUIs
                first_true_pos = torch.nonzero(self._valid_names[row_sorted], as_tuple=True)[0][0].item()

                # Get global index + name
                top_name_idx = row_sorted[first_true_pos].item()
                similarity = names_scores[i, top_name_idx].item()
                detected_name = self.name_keys[top_name_idx]
                cuis = self.cdb.name2info[detected_name]["per_cui_status"]

                # Disambiguate by CUI
                predicted_cui, _ = self._disambiguate_by_cui(
                    cuis, cui_scores[i,:]
                )

            entity.cui = predicted_cui        
            entity.context_similarity = similarity

            yield entity
        
    def _inference_by_cui(
            self, 
            doc: MutableDocument,
            entities: list[MutableEntity]
            ) -> Iterator[MutableEntity]:
        """Infer all entities at once (or in batches), to avoid multiple gpu calls when it isn't nessescary.
        Args:
            doc (BaseDocument): The document look in.
            name_keys (list[str]): list of all names2info
            cui_keys (list[str]): list of all cuis2info
            context_matrix: Tensor of context matrix we're planning to use 
            embedded from names in cui2info[cui]["preferred_name"]
        Yields:
            entity (MutableEntity): Entity with a relevant cui prediction - or skip if it's not suitable."""
        # 14 is a nice average between contexts in the context based linker
        detected_context_vectors = self._get_context_vectors(doc, entities, self.cnf_l.context_window_size)
        cui_to_idx = {cui: idx for idx, cui in enumerate(self.cui_keys)}
        # score all detected contexts vs all cui preferred names, handle in the loop each individual case
        scores = detected_context_vectors @ self.cui_context_matrix.T
        sorted_indices = torch.argsort(scores, dim=1, descending=True)
        for i, entity in enumerate(entities):
            # might as well filter here rather than later
            link_candidates = [cui for cui in entity.link_candidates if self.cnf_l.filters.check_filters(cui)]
            if self.cnf_l.use_ner_link_candidates and len(link_candidates) == 1:
                best_idx = cui_to_idx[link_candidates[0]]
                entity.cui = link_candidates[0]
                
                similarity = scores[i, best_idx].item()
                entity.context_similarity = similarity
            elif self.cnf_l.use_ner_link_candidates and len(link_candidates) > 1:
                predicted_cui, similarity = self._disambiguate_by_cui(
                    link_candidates,
                    scores[i,:]
                )
                entity.cui = predicted_cui        
                entity.context_similarity = similarity
            else:
                # no link candidates -> i.e. filtered or none from NER
                # therefore: score vs all cui preffered names!
                top_cui_idx = sorted_indices[i, 0].item()
                entity.cui = self.cui_keys[top_cui_idx]
                entity.context_similarity = scores[i, top_cui_idx].item()

            yield entity
            
    def _check_similarity(self, cui: str, context_similarity: float) -> bool:
        th_type = self.cnf_l.similarity_threshold_type
        threshold = self.cnf_l.similarity_threshold
        if th_type == 'static':
            return context_similarity >= threshold
        if th_type == 'dynamic':
            conf = self.cdb.cui2info[cui]['average_confidence']
            return context_similarity >= conf * threshold
        return False
    
    def _last_token_pool(self, last_hidden_states: Tensor,
                 attention_mask: Tensor) -> Tensor:
        left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
        if left_padding:
            return last_hidden_states[:, -1]
        else:
            sequence_lengths = attention_mask.sum(dim=1) - 1
            batch_size = last_hidden_states.shape[0]
            return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]
    
    def _build_context_matrices(self):
        self._name_keys = list(self.cdb.name2info)
        self._cui_keys = list(self.cdb.cui2info)
        
        if "name_embeddings" in self.cdb.addl_info:
            self._names_context_matrix = self.cdb.addl_info["name_embeddings"].half().to(self.device)
        if "cui_embeddings" in self.cdb.addl_info:
            self._cui_context_matrix = self.cdb.addl_info["cui_embeddings"].half().to(self.device)
        
    def __call__(self, doc: MutableDocument) -> MutableDocument:
        # Reset main entities, will be recreated later
        doc.linked_ents.clear()
        
        self._load_transformers(self.embedding_model_name)
        if self.cnf_l.train:
            logger.warning("Attemping to train an embedding linker. This is not required.")
            
        inference = self._inference_by_cui
        if self.cnf_l.linking_strategy == "names":
            inference = self._inference_by_names
            # filters are only done this way when infering by names
            self._set_filters()

        all_ents = doc.ner_ents
        le = []
        with torch.no_grad():
            for entities in self._batch_data(all_ents, self.cnf_l.linking_batch_size):
                le.extend(list(inference(doc, entities)))

        doc.ner_ents.clear()
        doc.ner_ents.extend(le)
        create_main_ann(doc)

        return doc
    
    @property
    def name_keys(self):
        if self._name_keys is None:
            self._build_context_matrices()
        return self._name_keys

    @property
    def cui_keys(self):
        if self._cui_keys is None:
            self._build_context_matrices()
        return self._cui_keys

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
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]
            ) -> 'Linker':
        return cls(cdb, cdb.config)