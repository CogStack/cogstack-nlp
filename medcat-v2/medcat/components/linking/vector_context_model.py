from typing import Optional, Iterable, Union, Sequence, cast, Callable
from typing import Protocol

import numpy as np
import random
import logging
from itertools import chain

from medcat.vocab import Vocab
from medcat.cdb.concepts import CUIInfo, NameInfo
from medcat.config.config import Linking
from medcat.tokenizing.tokens import (MutableToken, MutableEntity,
                                       MutableDocument)
from medcat.utils.defaults import StatusTypes as ST
from medcat.utils.matutils import unitvec
from medcat.storage.serialisables import AbstractSerialisable


logger = logging.getLogger(__name__)


class DisambPreprocessor(Protocol):

    def __call__(self, ent: MutableEntity, name: str, cuis: list[str],
                 similarities: list[float]) -> None:
        pass


class ContextModel(AbstractSerialisable):
    """Used to learn embeddings for concepts and calculate similarities
    in new documents.

    Args:
        cui2info (dict[str, CUIInfo]): The CUI to info mapping.
        name2info (dict[str, NameInfo]): The name to info mapping.
        weighted_average_function (Callable[[int], float]):
            The weighted average function.
        vocab (Vocab): The vocabulary
        config (Linking): The config to be used
        name_separator (str): The name separator
    """

    def __init__(self, cui2info: dict[str, CUIInfo],
                 name2info: dict[str, NameInfo],
                 weighted_average_function: Callable[[int], float],
                 vocab: Vocab, config: Linking,
                 name_separator: str,
                 disamb_preprocessors: list[DisambPreprocessor] = []) -> None:
        self.cui2info = cui2info
        self.name2info = name2info
        self.weighted_average_function = weighted_average_function
        self.vocab = vocab
        self.config = config
        self.name_separator = name_separator
        self._disamb_preprocessors = (  # copy if default/empty
            disamb_preprocessors or disamb_preprocessors.copy())

    def get_context_tokens(self, entity: MutableEntity, doc: MutableDocument,
                           size: int,
                           per_doc_valid_token_cache: 'PerDocumentTokenCache',
                           ) -> tuple[list[MutableToken],
                                      list[MutableToken],
                                      list[MutableToken]]:
        """Get context tokens for an entity, this will skip anything that
        is marked as skip in token._.to_skip

        Args:
            entity (BaseEntity): The entity to look for.
            doc (BaseDocument): The document look in.
            size (int): The size of the entity.
            per_doc_valid_token_cache (PerDocumentTokenCache):
                Per document cache for token validation.

        Returns:
            tuple[list[BaseToken], list[BaseToken], list[BaseToken]]:
                The tokens on the left, centre, and right.
        """
        start_ind = entity.base.start_index
        end_ind = entity.base.end_index

        _left_tokens = doc[max(0, start_ind - size):start_ind]
        tokens_left = [tkn for tkn in _left_tokens if
                       per_doc_valid_token_cache[tkn]]
        # Reverse because the first token should be the one closest to center
        tokens_left.reverse()
        tokens_center: list[MutableToken] = list(
            cast(Iterable[MutableToken], entity))
        _right_tokens = doc[end_ind + 1:end_ind + 1 + size]
        tokens_right = [tkn for tkn in _right_tokens if
                        per_doc_valid_token_cache[tkn]]

        return tokens_left, tokens_center, tokens_right

    def _tokens2vecs(self, tokens: Sequence[Union[MutableToken, str]]
                     ) -> Iterable[np.ndarray]:
        for step, tkn in enumerate(tokens):
            lower = tkn.lower() if isinstance(tkn, str) else tkn.base.lower
            if lower not in self.vocab:
                continue
            vec = self.vocab.vec(lower)
            if vec is not None:
                yield vec * self.weighted_average_function(step)

    def _should_change_name(self, cui: str) -> bool:
        target = self.config.random_replacement_unsupervised
        if random.random() <= target:
            return False
        return bool(self.cui2info.get(cui, None))

    def _preprocess_center_tokens(self, cui: Optional[str],
                                  tokens_center: list[MutableToken]
                                  ) -> Iterable[np.ndarray]:
        if cui is not None and self._should_change_name(cui):
            new_name: str = random.choice(list(self.cui2info[cui]['names']))
            new_tokens_center = new_name.split(self.name_separator)
            return self._tokens2vecs(new_tokens_center)
        else:
            return self._tokens2vecs(tokens_center)

    def get_context_vectors(self, entity: MutableEntity,
                            doc: MutableDocument,
                            per_doc_valid_token_cache: 'PerDocumentTokenCache',
                            cui: Optional[str] = None,
                            ) -> dict[str, np.ndarray]:
        """Given an entity and the document it will return the context
        representation for the given entity.

        Args:
            entity (BaseEntity): The entity to look for.
            doc (BaseDocument): The document to look in.
            per_doc_valid_token_cache (PerDocumentTokenCache):
                Per documnet cache for token validation
            cui (Optional[str]): The CUI or None if not specified.

        Returns:
            dict[str, np.ndarray]: The context vector.
        """
        vectors: dict[str, np.ndarray] = {}

        context_vector_sizes = self.config.context_vector_sizes
        for context_type, window_size in context_vector_sizes.items():
            tokens_left, tokens_center, tokens_right = self.get_context_tokens(
                entity, doc, window_size, per_doc_valid_token_cache)

            values: list[np.ndarray] = []
            # Add left
            values.extend(self._tokens2vecs(tokens_left))

            if not self.config.context_ignore_center_tokens:
                # Add center
                values.extend(
                    self._preprocess_center_tokens(cui, tokens_center))

            # Add right
            values.extend(self._tokens2vecs(tokens_right))

            if values:
                value = np.average(values, axis=0)
                vectors[context_type] = value
        return vectors

    def similarity(self, cui: str, entity: MutableEntity, doc: MutableDocument,
                   per_doc_valid_token_cache: 'PerDocumentTokenCache'
                   ) -> float:
        """Calculate the similarity between the learnt context for this CUI
        and the context in the given `doc`.

        Args:
            cui (str): The CUI.
            entity (BaseEntity): The entity to look for.
            doc (BaseDocument): The document to look in.
            per_doc_valid_token_cache (PerDocumentTokenCache):
                Per document cache for valid tokens

        Returns:
            float: The similarity.
        """
        vectors = self.get_context_vectors(
            entity, doc, per_doc_valid_token_cache)
        sim = self._similarity(cui, vectors)

        return sim

    def _similarity(self, cui: str, vectors: dict) -> float:
        """Calculate similarity once we have vectors and a cui.

        Args:
            cui (str): The CUI.
            vectors (dict): The vectors.

        Returns:
            float: The similarity.
        """
        cui_info = self.cui2info[cui]

        cui_vectors = cui_info['context_vectors']

        train_threshold = self.config.train_count_threshold
        if cui_vectors and cui_info['count_train'] >= train_threshold:
            return get_similarity(cui_vectors, vectors,
                                  self.config.context_vector_weights,
                                  cui, self.cui2info)
        else:
            return -1

    def _preprocess_disamb_similarities(self, entity: MutableEntity,
                                        name: str, cuis: list[str],
                                        similarities: list[float]) -> None:
        for preprocessor in self._disamb_preprocessors:
            preprocessor(entity, name, cuis, similarities)
        # NOTE: Has side effects on similarities
        if self.config.prefer_primary_name > 0:
            logger.debug("Preferring primary names")
            for i, (cui, sim) in enumerate(zip(cuis, similarities)):
                if sim <= 0:
                    continue
                status = self.name2info[name]['per_cui_status'].get(
                    cui, ST.AUTOMATIC)
                if status in ST.PRIMARY_STATUS:
                    new_sim = sim * (1 + self.config.prefer_primary_name)
                    similarities[i] = float(min(0.99, new_sim))
                    # DEBUG
                    logger.debug("CUI: %s, Name: %s, Old sim: %.3f, New "
                                 "sim: %.3f", cui, name, sim, similarities[i])

        if self.config.prefer_frequent_concepts > 0:
            logger.debug("Preferring frequent concepts")
            #  Prefer frequent concepts
            cnts = [self.cui2info[cui]['count_train'] for cui in cuis]
            m = min(cnts) or 1
            pref_freq = self.config.prefer_frequent_concepts
            scales = [np.log10(cnt / m) * pref_freq if cnt > 10 else 0
                      for cnt in cnts]
            old_sims = list(similarities)
            similarities.clear()
            similarities += [float(min(0.99, sim + sim * scale))
                             for sim, scale in zip(old_sims, scales)]

    def get_all_similarities(self, cuis: list[str], entity: MutableEntity,
                             name: str, doc: MutableDocument,
                             per_doc_valid_token_cache: 'PerDocumentTokenCache'
                             ) -> tuple[Union[list[str], list[None]],
                                        list[float], int]:
        vectors = self.get_context_vectors(
            entity, doc, per_doc_valid_token_cache)
        filters = self.config.filters

        # If it is trainer we want to filter concepts before disambiguation
        # do not want to explain why, but it is needed.
        if self.config.filter_before_disamb:
            # DEBUG
            logger.debug("Is trainer, subsetting CUIs")
            logger.debug("CUIs before: %s", cuis)

            cuis = [cui for cui in cuis if filters.check_filters(cui)]
            # DEBUG
            logger.debug("CUIs after: %s", cuis)

        if cuis:    # Maybe none are left after filtering
            # Calculate similarity for each cui
            similarities = [float(self._similarity(cui, vectors))
                            for cui in cuis]
            # DEBUG
            logger.debug("Similarities: %s", list(zip(cuis, similarities)))

            self._preprocess_disamb_similarities(
                entity, name, cuis, similarities)

            # technically, could be a np.int64 or something like that
            mx = int(np.argmax(similarities))
            return cuis, similarities, mx
        else:
            return [None], [0], 0

    def disambiguate(self, cuis: list[str], entity: MutableEntity, name: str,
                     doc: MutableDocument,
                     per_doc_valid_token_cache: 'PerDocumentTokenCache'
                     ) -> tuple[Optional[str], float]:
        suitable_cuis, sims, best_index = self.get_all_similarities(
            cuis, entity, name, doc, per_doc_valid_token_cache)
        return suitable_cuis[best_index], sims[best_index]

    def train(self, cui: str, entity: MutableEntity, doc: MutableDocument,
              per_doc_valid_token_cache: 'PerDocumentTokenCache',
              negative: bool = False, names: Union[list[str], dict] = [],
              ) -> None:
        """Update the context representation for this CUI, given it's correct
        location (entity) in a document (doc).

        Args:
            cui (str): The CUI to train.
            entity (BaseEntity): The entity we're at.
            doc (BaseDocument): The document within which we're working.
            per_doc_valid_token_cache (PerDocumentTokenCache):
                Per document cache for token validation.
            negative (bool): Whether or not the example is negative.
                Defaults to False.
            names (list[str]/dict):
                Optionally used to update the `status` of a name-cui
                pair in the CDB.
        """
        # Context vectors to be calculated
        if len(entity) == 0:  # Make sure there is something
            logger.warning("The provided entity for cui <%s> was empty, "
                           "nothing to train", cui)
            return
        vectors = self.get_context_vectors(
            entity, doc, per_doc_valid_token_cache, cui=cui)
        cui_info = self.cui2info[cui]
        lr = get_lr_linking(self.config, cui_info['count_train'])
        if not cui_info['context_vectors']:
            if not negative:
                cui_info['context_vectors'] = vectors
            else:
                cui_info['context_vectors'] = {ct: -1 * vec for
                                               ct, vec in vectors.items()}
        else:
            update_context_vectors(
                cui_info['context_vectors'], cui, vectors, lr,
                negative=negative)
        if not negative:
            cui_info['count_train'] += 1
        # Debug
        logger.debug("Updating CUI: %s with negative=%s", cui, negative)

        if not negative:
            # Update the name count, if possible
            if entity.detected_name:
                self.name2info[entity.detected_name]['count_train'] += 1

            if self.config.calculate_dynamic_threshold:
                # Update average confidence for this CUI
                sim = self.similarity(
                    cui, entity, doc, per_doc_valid_token_cache)
                new_conf = get_updated_average_confidence(
                    cui_info['average_confidence'],
                    cui_info['count_train'], sim)
                cui_info['average_confidence'] = new_conf

        if negative:
            # Change the status of the name so that it has
            # to be disambiguated always
            for name in names:
                if name not in self.name2info:
                    continue
                per_cui_status = self.name2info[name]['per_cui_status']
                cui_status = per_cui_status.get(cui, None)
                if cui_status == ST.PRIMARY_STATUS_NO_DISAMB:
                    # Set this name to always be disambiguated, even
                    # though it is primary
                    per_cui_status[cui] = ST.PRIMARY_STATUS_W_DISAMB
                    # Debug
                    logger.debug("Updating status for CUI: %s, "
                                 "name: %s to <%s>", cui, name,
                                 ST.PRIMARY_STATUS_W_DISAMB)
                elif cui_status == ST.AUTOMATIC:
                    # Set this name to always be disambiguated instead of A
                    per_cui_status[cui] = ST.MUST_DISAMBIGATE
                    logger.debug("Updating status for CUI: %s, "
                                 "name: %s to <N>", cui, name)
        if not negative and self.config.devalue_linked_concepts:
            # Find what other concepts can be disambiguated against this
            _other_cuis_chain = chain(*[
                self.name2info[name]['per_cui_status'].keys()
                for name in self.cui2info[cui]['names']])
            # Remove the cui of the current concept
            _other_cuis = set(_other_cuis_chain) - {cui}

            for _cui in _other_cuis:
                info = self.cui2info[_cui]
                if not info['context_vectors']:
                    info['context_vectors'] = vectors
                else:
                    update_context_vectors(
                        info['context_vectors'], cui, vectors, lr,
                        negative=True)

            logger.debug("Devalued via names.\n\tBase cui: %s \n\t"
                         "To be devalued: %s\n", cui, _other_cuis)

    def train_using_negative_sampling(self, cui: str) -> None:
        vectors = {}

        # Get vectors for each context type
        for context_type, size in self.config.context_vector_sizes.items():
            # While it should be size*2 it is already too many negative
            # examples, so we leave it at size
            ignore_pn = self.config.negative_ignore_punct_and_num
            inds = self.vocab.get_negative_samples(
                size, ignore_punct_and_num=ignore_pn)
            # NOTE: all indices in negative sampling have vectors
            #       since that's how they're generated
            values: list[np.ndarray] = self.vocab.get_vectors(inds)
            if len(values) > 0:
                vectors[context_type] = np.average(values, axis=0)
            # Debug
            logger.debug("Updating CUI: %s, with %s negative words",
                         cui, len(inds))

        cui_info = self.cui2info[cui]
        lr = get_lr_linking(self.config, cui_info['count_train'])
        # Do the update for all context types
        if not cui_info['context_vectors']:
            cui_info['context_vectors'] = vectors
        else:
            update_context_vectors(cui_info['context_vectors'], cui, vectors,
                                   lr, negative=True)


class PerDocumentTokenCache(dict[MutableToken, bool]):

    def __getitem__(self, key: MutableToken):
        index = key.base.index
        if index not in self:
            val = (not key.to_skip and not key.base.is_stop and
                   not key.base.is_digit and not key.is_punctuation)
            # NOTE: internally just using the token index
            self[index] = val  # type: ignore
            return val
        # NOTE: internally just using the token index
        return super().__getitem__(index)  # type: ignore


def get_lr_linking(config: Linking, cui_count: int) -> float:
    if config.optim['type'] == 'standard':
        return config.optim['lr']
    elif config.optim['type'] == 'linear':
        lr = config.optim['base_lr']
        cui_count += 1  # Just in case increase by 1
        return max(lr / cui_count, config.optim['min_lr'])
    else:
        raise Exception("Optimizer not implemented")


def get_similarity(cur_vectors: dict[str, np.ndarray],
                   other: dict[str, np.ndarray],
                   weights: dict[str, float], cui: str,
                   cui2info: dict[str, CUIInfo]) -> float:
    sim = 0
    for vec_type in weights:
        if vec_type not in other:
            # NOTE: sometimes the smaller context context types
            #       are unable to capture tokens that are present
            #       in our voab, which means they don't produce
            #       a value to be used here.
            continue
        if vec_type not in cur_vectors:
            # NOTE: this means that the saved vector doesn't have
            #       context at this vector type. This should be a
            #       rare occurrence, but is definitely present in
            #       models converted from v1
            continue
        w = weights[vec_type]
        v1 = cur_vectors[vec_type]
        v2 = other[vec_type]
        s = np.dot(unitvec(v1), unitvec(v2))
        sim += w * s
        logger.debug("Similarity for CUI: %s, Count: %s, Context Type: %.10s, "
                     "Weight: %s.2f, Similarity: %s.3f, S*W: %s.3f",
                     cui, cui2info[cui]['count_train'], vec_type, w, s, s * w)
    return float(sim)


def update_context_vectors(to_update: dict[str, np.ndarray], cui: str,
                           new_vecs: dict[str, np.ndarray], lr: float,
                           negative: bool) -> None:
    similarity = None
    for context_type, vector in new_vecs.items():
        # Get the right context
        if context_type in to_update:
            cv = to_update[context_type]
            similarity = np.dot(unitvec(cv), unitvec(vector))

            if negative:
                # Add negative context
                b = max(0, similarity) * lr
                to_update[context_type] = cv * (1 - b) - vector * b
            else:
                b = (1 - max(0, similarity)) * lr
                to_update[context_type] = cv * (1 - b) + vector * b

            # DEBUG
            logger.debug("Updated vector embedding.\n"
                         "CUI: %s, Context Type: %s, Similarity: %.2f, "
                         "Is Negative: %s, LR: %.5f, b: %.3f", cui,
                         context_type, similarity, negative, lr, b)
            cv = to_update[context_type]
            similarity_after = np.dot(unitvec(cv), unitvec(vector))
            logger.debug("Similarity before vs after: %.5f vs %.5f",
                         similarity, similarity_after)
        else:
            if negative:
                to_update[context_type] = -1 * vector
            else:
                to_update[context_type] = vector

            # DEBUG
            logger.debug("Added new context type with vectors.\n" +
                         "CUI: %s, Context Type: %s, Is Negative: %s",
                         cui, context_type, negative)


def get_updated_average_confidence(cur_ac: float, cnt_train: int,
                                   new_sim: float) -> float:
    return (cur_ac * cnt_train + new_sim) / (cnt_train + 1)
