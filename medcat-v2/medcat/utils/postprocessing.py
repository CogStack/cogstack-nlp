from medcat.tokenizing.tokenizers import MutableDocument, MutableEntity


# NOTE: the following used (in medcat v1) check tuis
#       but they were never passed to the method so
#       I've omitted it now
def create_main_ann(doc: MutableDocument, show_nested_entities: bool = False) -> None:
    """Creates annotation in the spacy ents list
    from all the annotations for this document.

    Args:
        doc (Doc): Spacy document.
        show_nested_entities (bool): Whether to keep overlapping/nested entities.
            If True, keeps all entities. If False, filters overlapping entities
            keeping only the longest matches. Defaults to False.
    """
    if show_nested_entities:
        doc.linked_ents = sorted(list(doc.linked_ents) + doc.ner_ents,  # type: ignore
                                 key=lambda ent: ent.base.start_char_index)
    else:
        # Filter overlapping entities using token indices (not object identity)
        doc.ner_ents.sort(key=lambda x: len(x.base.text), reverse=True)
        tkns_in = set()  # Set of token indices
        main_anns: list[MutableEntity] = []

        for ent in doc.ner_ents:
            to_add = True
            for tkn in ent:
                if tkn.base.index in tkns_in:  # Use token index instead
                    to_add = False
                    break
            if to_add:
                for tkn in ent:
                    tkns_in.add(tkn.base.index)
                main_anns.append(ent)

        # unclear why the original doc.linked_ents needs to be preserved here.
        doc.linked_ents = sorted(list(doc.linked_ents) + main_anns,  # type: ignore
                                 key=lambda ent: ent.base.start_char_index)

