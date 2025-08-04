from medcat.cdb import CDB
from medcat.config.config import Config, ComponentConfig
from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.tokenizing.tokens import MutableEntity, MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from typing import Optional, Iterator, Any
from medcat.vocab import Vocab
from torch import Tensor
from transformers import AutoTokenizer, AutoModel
from medcat.utils.postprocessing import create_main_ann
from tqdm import tqdm
from medcat.tokenizing.spacy_impl.tokens import Entity
import torch.nn.functional as F
import torch
import logging
import numpy as np
import math 
import copy
logger = logging.getLogger(__name__)

class Linker(AbstractCoreComponent):
    name = "embedding_linker"
    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    # NOTE: NEED TO IMPLEMENT 
    # the arguments provide to the init method in order
    @classmethod
    def get_init_args(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                      model_load_path: Optional[str]) -> list[Any]:
            extra = cdb.config.components.linking.additional or {}
            emb_name  = extra.get("embedding_model_name", cls.DEFAULT_MODEL)
            max_len   = extra.get("max_length", 64)
            return [
                cdb, 
                cdb.config, 
                emb_name, 
                max_len
            ]

    # NOTE: NEED TO IMPLEMENT
    # the keyword arguments to the init method
    @classmethod
    def get_init_kwargs(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                        model_load_path: Optional[str]) -> dict[str, Any]:
        extra = cdb.config.components.linking.additional or {}
        emb_name  = extra.get("embedding_model_name", cls.DEFAULT_MODEL)
        max_len   = extra.get("max_length", 64)
        return {
            "cdb": cdb,
            "config": cdb.config,
            "embedding_model_name": emb_name,
            "max_length": max_len,
        }

    def __init__(self, 
                 cdb: CDB, 
                 config: Config,
                 embedding_model_name: str = DEFAULT_MODEL,
                 max_length = 64,) -> None:
        """Initializes the embedding linker with a CDB and configuration.
        Args:
            cdb (CDB): The concept database to use.
            config (Config): The base config.
            embedding_model_name (Optional[str]): The name of the embedding model to use. Default is "sentence-transformers/all-MiniLM-L6-v2"
            max_length (int): The maximum length of the input sequences for the embedding model. Default is 64.
        """
        self.cdb = cdb
        self.config = config
        self.max_length = max_length 
        self.embedding_model_name = embedding_model_name
        extra = self.cdb.config.components.linking.additional or {}
        extra.setdefault("embedding_model_name", self.DEFAULT_MODEL)
        extra.setdefault("max_length", max_length)

    def embed_names(self, embedding_model_name: str, batch_size: int = 4096) -> None:
        """Obtain embeddings for all names in the CDB using the specified
        embedding model and store them in the name2info.context_vectors
        Args:
            embedding_model_name (str): The name of the embedding model to use.
            batch_size (int): The size of the batches to use when embedding names. Default 4096
        """
        if embedding_model_name == self.embedding_model_name:
            logger.debug("Using the same embedding model for training.")
        else:
            self.embedding_model_name = embedding_model_name
        self._load_transformers(embedding_model_name)
        names = list(self.cdb.name2info.keys())
        # embed each name in batches. Because there can be 3+ million names
        total_batches = math.ceil(len(names) / batch_size)
        for names in tqdm(self._batch_data(names, batch_size), total=total_batches + 1, desc="Embedding names"):
            with torch.no_grad():
                # removing ~ from names, as it is used to indicate a space in the CDB
                names_to_embed = [name.replace("~", " ") for name in names]
                batch_dict = self.tokenizer(names_to_embed, max_length=self.max_length, padding=True, truncation=True, return_tensors='pt').to(self.device)
                outputs = self.model(**batch_dict)
                embeddings = self._last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
                embeddings = F.normalize(embeddings, p=2, dim=1)
            for name, embedding in zip(names, embeddings):
                name_info = self.cdb.name2info[name]
                name_info["context_vectors"] = embedding.cpu()
                self.cdb.name2info[name] = name_info
        logger.debug("Embedding names done, total: %d", len(names))
    

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking
    
    def _batch_data(self, data, batch_size=4096) -> Iterator[list]:
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]

    def _load_transformers(self, 
                           embedding_model_name: str = DEFAULT_MODEL) -> None:
        """Load the transformers model and tokenizer.
        No need to load a transformer model until it's required.
        Args:
            embedding_model_name (str): The name of the embedding model to load. Default is "sentence-transformers/all-MiniLM-L6-v2"
        """
        if not hasattr(self, "model") or not hasattr(self, "tokenizer") or embedding_model_name != self.embedding_model_name:
            self.embedding_model_name = embedding_model_name
            self.tokenizer = AutoTokenizer.from_pretrained(embedding_model_name)
            self.model = AutoModel.from_pretrained(embedding_model_name)
            self.model.eval()
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(self.device)
            logger.debug(f"Loaded embedding model: {embedding_model_name} on device: {self.device}")

    def _score_names(self, names_to_score: list[str]):
        """Predicts the appropriate names for detected names comparing embedding similarity
        Args:
            name (str): The detected name to score.
        Returns:
            list[tuple[str, float, Tensor]]: A list of tuples containing the predicted name, similarity, and embedding."""
        if not hasattr(self, "context_matrix"):
            raise ValueError("Embeddings have not been initialised. Please run `cat._pipeline._components[-1].embed_names` first.")
        
        with torch.no_grad():
            batch_dict = self.tokenizer(names_to_score, max_length=self.max_length, padding=True, truncation=True, return_tensors='pt').to(self.device)
            outputs = self.model(**batch_dict)
            detected_name_embeddings = self._last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
            detected_name_embeddings = F.normalize(detected_name_embeddings, p=2, dim=1)
            scores = detected_name_embeddings @ self.context_matrix.T

        argmax_indices = torch.argmax(scores, dim=1)
        predicted_names = [self.names[i] for i in argmax_indices]
        max_similarities = scores.gather(1, argmax_indices.unsqueeze(1)).squeeze(1)
        return [
            (pred_name, score.item(), emb.cpu())
            for pred_name, score, emb in zip(predicted_names, max_similarities, detected_name_embeddings)
        ]
    
    def _disambiguate_entity_by_vector_similarity(self, 
                                                  potential_name_cui_pairs: list[tuple[str, str]],
                                                  detected_name_embedding: Tensor) -> str:
        """Disambiguate entities based on vector similarity.
        If there are multiple potential cuis, try to find the one with the highest similarity to the detected name.
        Args:
            name (str): The detected name.
            potential_name_cui_pairs (list[tuple[str, str]]): List of tuples containing CUI and preferred name pairs.
            name_embedding (Tensor): The embedding of the detected name.
        Returns:
            str: The CUI with the highest similarity to the detected name.
        """
        names = [name for _, name in potential_name_cui_pairs]
        # we have to embed CUI preferred names because they might not exist
        batch_dict = self.tokenizer(names, max_length=self.max_length, padding=True, truncation=True, return_tensors='pt').to(self.device)
        outputs = self.model(**batch_dict)
        name_vectors = self._last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
        name_vectors = F.normalize(name_vectors, p=2, dim=1).cpu()
        scores = detected_name_embedding @ name_vectors.T
        best_idx = torch.argmax(scores).item()
        return potential_name_cui_pairs[best_idx][0]

        
    
    def _disambiguate_entity(self, 
                             entity: MutableEntity, 
                             cuis: list[str],
                             name_embedding: Tensor) -> str:
        """Disambiguation where multiple cuis are linked to the same name. 
        Try to choose the best one based on cui2preffered names.
        If there is multiple potential cuis still then try scoring the highest again
        Args:
            entity (MutableEntity): The entity to disambiguate.
            cui (str): The CUI to disambiguate to.
            embedding (Tensor): The embedding of the detected name.
        Returns:
            str: The disambiguated CUI.
        """
        # if theres only one CUI, just return it
        if len(cuis) == 1:
            return cuis[0]
        # collect all preferred name / cui pairs first
        potential_name_cui_pairs = [(cui, self.cdb.cui2info[cui]['preferred_name'].replace("~", " ")) for cui in cuis]
        # if there are multiple, try to find all that matches the detected name
        name = entity.detected_name or entity.base.text
        name = name.replace("~", " ")
        matching_cuis = [cui for cui, preferred_name in potential_name_cui_pairs if preferred_name.lower() == name.lower()]
        # if there are multiple matching, just return the first one
        # if there are mulitple preferred names then I'm not sure how to choose
        if len(matching_cuis) == 1:
            return matching_cuis[0][0]
        else:
            # no perfect names match, so disambiguate by vector similarities
            return self._disambiguate_entity_by_vector_similarity(potential_name_cui_pairs, name_embedding)

    def _process_entity_inference(
        self,
        entities: MutableEntity,
        ) -> Iterator[MutableEntity]:
        """Infer all entities at once (or in batches), to avoid multiple gpu calls when it isn't nessescary"""
        # I don't think we have to concern ourselves with link candidates from the NER step.
        # Check does it have a detected name, if not just use the base text
        names_to_score = [entity.detected_name or entity.base.text for entity in entities]
        names_to_score = [name.replace("~", " ") for name in names_to_score]
        results = self._score_names(names_to_score)

        for entity, (predicted_name, similarity, embedding) in zip(entities, results):
            # is there a better way to get cui2name mapping?
            # this isn't a one to one mapping, so we just take the first one
            predicted_cuis = list(self.cdb.name2info[predicted_name]["per_cui_status"].keys())
            # filter out unwanted cuis
            cnf_l = self.config.components.linking
            predicted_cuis = [cui for cui in predicted_cuis if cnf_l.filters.check_filters(cui)]
            # if there are no cuis, just skip the entity
            if not predicted_cuis:
                continue
            predicted_cui = self._disambiguate_entity(entity, predicted_cuis, embedding)
            entity.cui = predicted_cui        
            entity.context_similarity = similarity
            yield entity

    def _inference(self, doc: MutableDocument) -> Iterator[MutableEntity]:
        # doing this here so it isn't done on each entity
        self.names = list(self.cdb.name2info.keys())
        self.context_matrix = torch.stack([self.cdb.name2info[name]["context_vectors"] for name in self.cdb.name2info]).to(self.device)
        for entities in self._batch_data(doc.ner_ents):
            logger.debug("Linker started with entities: %s", len(entities))
            yield from self._process_entity_inference(entities)
            
    def _check_similarity(self, cui: str, context_similarity: float) -> bool:
        th_type = self.config.components.linking.similarity_threshold_type
        threshold = self.config.components.linking.similarity_threshold
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
        
    def __call__(self, doc: MutableDocument) -> MutableDocument:
        # Reset main entities, will be recreated later
        doc.linked_ents.clear()
        self._load_transformers(self.embedding_model_name)

        cnf_l = self.config.components.linking

        if cnf_l.train:
            logger.warning("Attemping to train an embedding linker. This is not required.")
        linked_entities = self._inference(doc)
        # evaluating generator here because the `all_ents` list gets
        # cleared afterwards otherwise
        le = list(linked_entities)

        doc.ner_ents.clear()
        doc.ner_ents.extend(le)
        create_main_ann(doc)

        return doc
        
    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]
            ) -> 'Linker':
        return cls(cdb, cdb.config)