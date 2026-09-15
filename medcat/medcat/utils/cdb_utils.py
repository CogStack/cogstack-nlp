from collections import defaultdict
import logging
from medcat.cdb.concepts import NameInfo
import numpy as np

from copy import deepcopy
from typing import Any, Iterable
from medcat.cdb import CDB

logger = logging.getLogger(__name__)  # separate logger from the package-level one


def merge_cdb(cdb1: CDB,
              cdb2: CDB,
              overwrite_training: int = 0,
              full_build: bool = False) -> CDB:
    """Merge two CDB's together to produce a new, single CDB. The contents of
    inputs CDBs will not be changed.
    `addl_info` can not be perfectly merged, and will prioritise cdb1. see `full_build`

    Args:
        cdb1 (CDB):
            The first medcat cdb to merge. In cases where merging isn't suitable
            isn't ideal (such as cui2preferred_name), this cdb values will be
            prioritised over cdb2.
        cdb2 (CDB):
            The second medcat cdb to merge.
        overwrite_training (int):
            Choose to prioritise a CDB's context vectors values over merging gracefully.
            0 - no prio, 1 - CDB1, 2 - CDB2
        full_build (bool):
            Add additional information from "addl_info" dicts "cui2ontologies" and
            "cui2description"

    Returns:
        CDB: The merged CDB.
    """
    config = deepcopy(cdb1.config)
    cdb = CDB(config)

    # Copy CDB 1 - as all settings from CDB 1 will be carried over
    cdb.cui2info = deepcopy(cdb1.cui2info)
    cdb.name2info = deepcopy(cdb1.name2info)
    cdb.type_id2info = deepcopy(cdb1.type_id2info)
    cdb.token_counts = deepcopy(cdb1.token_counts)
    cdb._subnames = deepcopy(cdb1._subnames)
    if full_build:
        cdb.addl_info = deepcopy(cdb1.addl_info)

    # Merge concepts from cdb2 into the merged CDB
    for cui, cui_info2 in cdb2.cui2info.items():
        # Get name status from cdb2
        name_status = 'A'  # default status
        for name in cui_info2['names']:
            if name in cdb2.name2info:
                name_info = cdb2.name2info[name]
                if cui in name_info['per_cui_status']:
                    name_status = name_info['per_cui_status'][cui]
                    break

        # Prepare names dict for _add_concept
        names = {}
        for name in cui_info2['names']:
            # Create a simple NameDescriptor-like structure
            name_info_entry: NameInfo | None = cdb2.name2info.get(name)
            names[name] = type('NameDescriptor', (), {
                'snames': cui_info2['subnames'],
                # Guard for unknown structure in name2info and avoid mismatched defaults
                'is_upper': (bool(name_info_entry.get('is_upper', False))
                    if isinstance(name_info_entry, dict) else False),
                'tokens': set(),  # We don't have token info in the new structure
                'raw_name': name
            })()

        # Get ontologies and description for full_build
        ontologies: set[str] = set()
        description = cui_info2.get('description') or ''
        to_build = full_build and (
            cui_info2.get('original_names') is not None or
            cui_info2.get('description') is not None
        )

        if to_build:
            other: Iterable[str] = cui_info2.get('in_other_ontology') or []
            ontologies.update(other)

        cdb._add_concept(
            cui=cui, names=names, ontologies=ontologies, name_status=name_status,
            type_ids=cui_info2['type_ids'], description=description,
            full_build=to_build
        )

        # Copy training data from cdb2 for concepts that don't exist in cdb1
        if cui not in cdb1.cui2info:
            cui_info_merged = cdb.cui2info[cui]
            cui_info_merged['count_train'] = cui_info2['count_train']
            cui_info_merged['context_vectors'] = deepcopy(cui_info2['context_vectors'])
            cui_info_merged['average_confidence'] = cui_info2['average_confidence']
            if cui_info2.get('tags'):
                cui_info_merged['tags'] = deepcopy(cui_info2['tags'])

        # Handle merging of training data for concepts that exist in both CDBs
        if cui in cdb1.cui2info:
            cui_info1 = cdb1.cui2info[cui]
            cui_info_merged = cdb.cui2info[cui]

            # Merge count_train
            if (cui_info1['count_train'] > 0 or cui_info2['count_train'] > 0) and not (
                overwrite_training == 1 and cui_info1['count_train'] > 0
            ):
                if overwrite_training == 2 and cui_info2['count_train'] > 0:
                    cui_info_merged['count_train'] = cui_info2['count_train']
                else:
                    cui_info_merged['count_train'] = (
                        cui_info1['count_train'] + cui_info2['count_train']
                    )

            # Merge context vectors
            if (cui_info1['context_vectors'] is not None and
                not (overwrite_training == 1 and
                     cui_info1['context_vectors'] is not None)):

                if (overwrite_training == 2 and
                    cui_info2['context_vectors'] is not None):
                    cui_info_merged['context_vectors'] = deepcopy(
                        cui_info2['context_vectors']
                    )
                else:
                    # Merge context vectors with weighted average
                    if cui_info_merged['context_vectors'] is None:
                        cui_info_merged['context_vectors'] = {}

                    # Get all context types from both CDBs
                    contexts: set[str] = set()
                    if cui_info1['context_vectors']:
                        contexts.update(cui_info1['context_vectors'].keys())
                    if cui_info2['context_vectors']:
                        contexts.update(cui_info2['context_vectors'].keys())

                    # Calculate weights
                    if overwrite_training == 2:
                        weights: list[float] = [0.0, 1.0]
                    else:
                        norm = cui_info_merged['count_train']
                        if norm > 0:
                            weights = [
                                np.divide(cui_info1['count_train'], norm),
                                np.divide(cui_info2['count_train'], norm)
                            ]
                        else:
                            weights = [0.5, 0.5]  # equal weights if no training

                    # Merge each context vector
                    for context_type in contexts:
                        if cui_info1['context_vectors']:
                            vec1 = cui_info1['context_vectors'].get(
                                context_type, np.zeros(300)
                            )
                        else:
                            vec1 = np.zeros(300)

                        if cui_info2['context_vectors']:
                            vec2 = cui_info2['context_vectors'].get(
                                context_type, np.zeros(300)
                            )
                        else:
                            vec2 = np.zeros(300)
                        cv: dict[str, np.ndarray] = cui_info_merged['context_vectors']  # type: ignore[assignment]
                        cv[context_type] = (weights[0] * vec1 + weights[1] * vec2)

            # Merge tags
            if cui_info1.get('tags') and cui_info2.get('tags'):
                if cui_info_merged.get('tags') is None:
                    cui_info_merged['tags'] = []
                dest_tags: list[str] = cui_info_merged['tags']  # type: ignore[assignment]
                src_tags = cui_info2.get('tags')
                if src_tags:
                    dest_tags.extend(src_tags)

            # Merge type_ids (already handled by _add_concept, but ensure union)
            cui_info_merged['type_ids'].update(cui_info2['type_ids'])

    # Merge name training counts
    if overwrite_training != 1:
        for name, name_info2 in cdb2.name2info.items():
            if name in cdb1.name2info and overwrite_training == 0:
                # Merge training counts for names that exist in both CDBs
                name_info1 = cdb1.name2info[name]
                name_info_merged = cdb.name2info[name]
                name_info_merged['count_train'] = (
                    name_info1['count_train'] + name_info2['count_train']
                )
            else:
                # Copy name info from cdb2 if it doesn't exist in cdb1
                if name not in cdb.name2info:
                    cdb.name2info[name] = deepcopy(name_info2)

    # Merge token counts
    if overwrite_training != 1:
        for token, count in cdb2.token_counts.items():
            if token in cdb.token_counts and overwrite_training == 0:
                cdb.token_counts[token] += count
            else:
                cdb.token_counts[token] = count

    return cdb


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    deduped_list = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped_list.append(item)
    return deduped_list


def get_all_ch(parent_cui: str, cdb):
    """Get all the children of a given parent CUI. Preserves the order of the parent

    Args:
        parent_cui (str): The parent CUI
        cdb (CDB): The CDB object

    Returns:
        list: The children of the parent CUI
    """
    all_ch = [parent_cui]
    for cui in cdb.addl_info.get('pt2ch', {}).get(parent_cui, []):
        cui_chs = get_all_ch(cui, cdb)
        all_ch += cui_chs
    return _dedupe_preserve_order(all_ch)


def ch2pt_from_pt2ch(cdb: CDB, pt2ch_key: str = 'pt2ch'):
    """Get the child to parent info from the pt2ch map in the CDB

    Args:
        cdb (CDB): The CDB object with addl_info['pt2ch']
        pt2ch_key (str, optional): The key in the addl_info dict to get the pt2ch map
            from.
            Defaults to 'pt2ch'.
    Returns:
        dict: The child to parent info
    """
    ch2pt = defaultdict(list)
    for k, vals in cdb.addl_info[pt2ch_key].items():
        for v in vals:
            ch2pt[v].append(k)
    return ch2pt


def snomed_ct_concept_path(
    cui: str, cdb: CDB, parent_node='138875005'
) -> dict[str, Any]:
    """Get the concept path for a given CUI to a parent node

    Args:
        cui (str): The CUI of the concept to get the path for
        cdb (CDB): The CDB object
        parent_node (str, optional): The top level parent node.
            Defaults to '138875005' the root SNOMED CT code.

    Returns:
        dict: The concept path and links
    """
    try:
        def find_parents(cui, cuis2nodes, child_node=None):
            parents = list(cdb.addl_info.get('ch2pt', {}).get(cui, []))
            all_links = []
            if cui not in cuis2nodes:
                # Get preferred name from the new CDB structure
                preferred_name = cdb.get_name(cui)
                curr_node = {'cui': cui, 'pretty_name': preferred_name}
                if child_node:
                    curr_node['children'] = [child_node]
                cuis2nodes[cui] = curr_node
                if len(parents) > 0:
                    all_links += find_parents(
                        parents[0], cuis2nodes, child_node=curr_node
                    )
                    for p in parents[1:]:
                        links = find_parents(p, cuis2nodes)
                        all_links += [{'parent': p, 'child': cui}] + links
            else:
                if child_node:
                    if 'children' not in cuis2nodes[cui]:
                        cuis2nodes[cui]['children'] = []
                    cuis2nodes[cui]['children'].append(child_node)
            return all_links
        cuis2nodes: dict[str, dict[str, Any]] = {}
        all_links = find_parents(cui, cuis2nodes)
        return {
            'node_path': cuis2nodes[parent_node],
            'links': all_links
        }
    except KeyError as e:
        logger.error(f'Cannot find path concept path for CUI: {cui}',
            exc_info=True)
        return {'node_path': {}, 'links': []}
