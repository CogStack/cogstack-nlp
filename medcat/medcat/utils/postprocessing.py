import warnings

from medcat.tokenizing.tokenizers import MutableDocument, MutableEntity


def create_main_ann(doc: MutableDocument, show_nested_entities: bool = False) -> None:
    warnings.warn(
        "The `medcat.utils.postprocessing.create_main_ann` method is"
        "depreacated and subject to removal in a future release. Please "
        "use `medcat.utils.postprocessing.filter_linked_annotations` instead.",
        DeprecationWarning,
        stacklevel=2
    )
    doc.linked_ents = filter_linked_annotations(  # type: ignore
        doc, doc.ner_ents, show_nested_entities=show_nested_entities)


# NOTE: the following used (in medcat v1) check tuis
#       but they were never passed to the method so
#       I've omitted it now
def filter_linked_annotations(
        doc: MutableDocument,
        linked_ents: list[MutableEntity],
        show_nested_entities: bool = False
        ) -> list[MutableEntity]:
    """Creates annotation in the spacy ents list
    from all the annotations for this document.

    Args:
        doc (Doc): Spacy document.
        linked_ents (list[MutableEntity]): The linked entities.
        show_nested_entities (bool): Whether to keep overlapping/nested entities.
            If True, keeps all entities. If False, filters overlapping entities
            keeping only the longest matches. Defaults to False.

    Returns:
        list[MutbaleEntity]: The resulting entities
    """
    if show_nested_entities:
        return sorted(list(linked_ents),
                      key=lambda ent: ent.base.start_char_index)
    else:
        # Filter overlapping entities using token indices (not object identity)
        linked_ents.sort(key=lambda x: len(x.base.text), reverse=True)
        tkns_in = set()  # Set of token indices
        main_anns: list[MutableEntity] = []

        for ent in linked_ents:
            to_add = True
            for tkn in ent:
                if tkn.base.index in tkns_in:  # Use token index instead
                    to_add = False
                    break
            if to_add:
                for tkn in ent:
                    tkns_in.add(tkn.base.index)
                main_anns.append(ent)

        return sorted(main_anns,
                      key=lambda ent: ent.base.start_char_index)
