from typing import Callable, Optional
from typing_extensions import Self
from contextlib import contextmanager
import logging

from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.components.types import (
    CoreComponentType, AbstractEntityProvidingComponent)
from medcat.components.ner.vocab_based_ner import tokens_to_raw_name_opts
from medcat.config.config import ComponentConfig
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import (
    MutableDocument, MutableEntity, MutableToken, UNTOKENIZABLE_ENTITY_ID,
)
from medcat.data.mctexport import (
    MedCATTrainerExport, MedCATTrainerExportDocument, count_all_docs, iter_docs)
from medcat.vocab import Vocab


logger = logging.getLogger(__name__)


class _CheatingComponent(AbstractEntityProvidingComponent):
    name = 'cheating_component'

    def __init__(self,
            comp_type: CoreComponentType,
            predictor: Callable[[MutableDocument], list[MutableEntity]]):
        self._comp_type = comp_type
        super().__init__(
            comp_type == CoreComponentType.linking,
            comp_type == CoreComponentType.linking)
        self._predictor = predictor

    def get_type(self) -> CoreComponentType:
        return self._comp_type

    def predict_entities(self, doc: MutableDocument,
                         ents: list[MutableEntity] | None = None
                         ) -> list[MutableEntity]:
        return self._predictor(doc)

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]) -> Self:
        raise ValueError("Cannot create new component of this type")


@contextmanager
def cheating_component(
        cat: CAT,
        comp_type: CoreComponentType,
        predictor: Callable[[MutableDocument], list[MutableEntity]]):
    """Creates and uses a cheating component within the pipe.

    This component will "predict" entities as per the predictor it is given.

    Args:
        cat (CAT): The model pack.
        comp_type (CoreComponentType): The component type (generally NER or linker).
        predictor (Callable[[MutableDocument], list[MutableEntity]]):
            The predictor to use.
    """
    comps_list = cat.pipe._components
    # find original index
    original_comp = cat.pipe.get_component(comp_type)
    replace_index = comps_list.index(original_comp)
    # create and replace
    cheater = _CheatingComponent(comp_type, predictor)
    comps_list[replace_index] = cheater
    try:
        yield
    finally:
        # restore original component
        comps_list[replace_index] = original_comp


def _identify_document(
        doc: MutableDocument,
        dataset: MedCATTrainerExport) -> MedCATTrainerExportDocument:
    for proj in dataset['projects']:
        for ann_doc in proj['documents']:
            if ann_doc['text'] == doc.base.text:
                return ann_doc
    raise ValueError("Unable to identify correct document")


def _parse_raw_name(
    tkns: list[MutableToken],
    separator: str,
    try_reverse_word_order: bool,
    checker: Callable[[str], bool],
) -> str:
    opts = tokens_to_raw_name_opts(
        tkns, separator, try_reverse_word_order)
    for opt in opts:
        if checker(opt):
            return opt
    # NOTE: redoing this for the sake of the exception,
    #       otherwise the iteration would be empty
    opts = tokens_to_raw_name_opts(
        tkns, separator, try_reverse_word_order)
    raise UnknownTokensException(
        f"Unable to turn tokens {tkns} into a name that exists in the CDB. "
        f"The options tried were: {list(opts)}."
    )


class UnknownTokensException(ValueError):
    pass


def _create_general_predictor(
    dataset: MedCATTrainerExport,
    tokens2entity: Callable[[list[MutableToken], MutableDocument], MutableEntity],
    tokens2name: Callable[[list[MutableToken]], str],
    name2candidates: Callable[[str], list[str]],
    set_cui: bool,
) -> Callable[[MutableDocument], list[MutableEntity]]:
    def predict(doc: MutableDocument) -> list[MutableEntity]:
        anns = _identify_document(doc, dataset)["annotations"]
        ents: list[MutableEntity] = []
        for ann in anns:
            start = ann["start"]
            end = ann["end"]
            tkns = doc.get_tokens(start, end)
            try:
                ent = tokens2entity(tkns, doc)
            except ValueError as e:
                logger.debug(
                    "Issue getting tokens for %s @ %s: %s. Attempt to "
                    "resolve by using a wider span.",
                    ann['cui'], str((start, end)),
                    doc.base.text[start: end],
                    exc_info=e,
                )
                while not tkns:
                    # If no tokens found, try expanding the 
                    # range by 1 character on each side
                    start = max(0, start - 1)
                    end = end + 1
                    tkns = doc.get_tokens(start, end)
                ent = tokens2entity(tkns, doc)
                ent.id = UNTOKENIZABLE_ENTITY_ID
            if set_cui:
                ent.cui = ann["cui"]
            else:
                name = tokens2name(tkns)
                ent.detected_name = name
                ent.link_candidates = name2candidates(name)
            ents.append(ent)
        return ents
    return predict


def _create_linker_predictor(
    dataset: MedCATTrainerExport,
    tokens2entity: Callable[[list[MutableToken], MutableDocument], MutableEntity],
    tokens2name: Callable[[list[MutableToken]], str],
    name2candidates: Callable[[str], list[str]],
) -> Callable[[MutableDocument], list[MutableEntity]]:
    return _create_general_predictor(
        dataset, tokens2entity, tokens2name, name2candidates, True)


def _create_ner_predictor(
    dataset: MedCATTrainerExport,
    tokens2entity: Callable[[list[MutableToken], MutableDocument], MutableEntity],
    tokens2name: Callable[[list[MutableToken]], str],
    name2candidates: Callable[[str], list[str]],
) -> Callable[[MutableDocument], list[MutableEntity]]:
    return _create_general_predictor(
        dataset, tokens2entity, tokens2name, name2candidates, False)


def _create_predictor(
    component_type: CoreComponentType,
    dataset: MedCATTrainerExport,
    tokens2entity: Callable[[list[MutableToken], MutableDocument], MutableEntity],
    tokens2name: Callable[[list[MutableToken]], str],
    name2candidates: Callable[[str], list[str]],
) -> Callable[[MutableDocument], list[MutableEntity]]:
    if component_type == CoreComponentType.linking:
        return _create_linker_predictor(
            dataset, tokens2entity, tokens2name, name2candidates)
    elif component_type == CoreComponentType.ner:
        return _create_ner_predictor(
            dataset, tokens2entity, tokens2name, name2candidates)
    raise ValueError(
        f"Unable to create predictor for component {component_type}")


def _check_dataset(dataset: MedCATTrainerExport):
    texts = set(
        doc['text'] for _, doc in iter_docs(dataset)
    )
    num_texts = len(texts)
    num_docs = count_all_docs(dataset)
    if num_texts != num_docs:
        raise ValueError(
            "Dataset contains documents with identical texts. "
            "This means it cannot be used for dataset aware components "
            "because the identification of the document is not trivial. "
            f"The check found {num_texts} different texts within {num_docs} "
            "documents")


@contextmanager
def dataset_aware_component(
        cat: CAT,
        comp_type: CoreComponentType,
        dataset: MedCATTrainerExport):
    """Creates and uses a dataset aware component within the pipe.

    This simplfies trainin for and evaluating one component at
    a time by swapping out the other component for one that has
    perfect performance since it knows the dataset.

    Args:
        cat (CAT): The model pack.
        comp_type (CoreComponentType): The component type.
        dataset (MedCATTrainerExport): The dataset in question.
    """
    _check_dataset(dataset)
    tokens2entity = cat.pipe.tokenizer.entity_from_tokens_in_doc

    def tokens2name(tkns: list[MutableToken]) -> str:
        sep = cat.config.general.separator
        try_reverse_order = cat.config.components.ner.try_reverse_word_order
        return _parse_raw_name(
            tkns, sep, try_reverse_order,
            lambda name: name in cat.cdb.name2info
        )

    def name2candidates(name: str) -> list[str]:
        # NOTE: the name should always be in there since we check
        #       for that within the candidates with `tokens2name`
        #       with the lambda
        return list(cat.cdb.name2info[name]['per_cui_status'])

    predictor = _create_predictor(
        comp_type, dataset, tokens2entity, tokens2name, name2candidates)
    with cheating_component(cat, comp_type, predictor):
        yield
