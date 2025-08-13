import logging
from collections import defaultdict
from typing import List

from medcat.cdb import CDB


logger = logging.getLogger(__name__)


def ch2pt_from_pt2ch(cdb: CDB):
    ch2pt = defaultdict(list)
    for k, vals in cdb.addl_info['pt2ch'].items():
        for v in vals:
            ch2pt[v].append(k)
    return ch2pt


def get_all_ch(parent_cui: str, cdb: CDB):
    all_ch = [parent_cui]
    for cui in cdb.addl_info['pt2ch'].get(parent_cui, []):
        cui_chs = get_all_ch(cui, cdb)
        all_ch += cui_chs
    return dedupe_preserve_order(all_ch)


def dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    deduped_list = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped_list.append(item)
    return deduped_list


def snomed_ct_concept_path(cui: str, cdb: CDB):
    try:
        top_level_parent_node = '138875005'

        def find_parents(cui, cuis2nodes, child_node=None):
            parents = list(cdb.addl_info['ch2pt'][cui])
            all_links = []
            if cui not in cuis2nodes:
                curr_node = {'cui': cui, 'pretty_name': cdb.cui2preferred_name[cui]}
                if child_node:
                    curr_node['children'] = [child_node]
                cuis2nodes[cui] = curr_node
                if len(parents) > 0:
                    all_links += find_parents(parents[0], cuis2nodes, child_node=curr_node)
                    for p in parents[1:]:
                        links = find_parents(p, cuis2nodes)
                        all_links += [{'parent': p, 'child': cui}] + links
            else:
                if child_node:
                    if 'children' not in cuis2nodes[cui]:
                        cuis2nodes[cui]['children'] = []
                    cuis2nodes[cui]['children'].append(child_node)
            return all_links
        cuis2nodes = dict()
        all_links = find_parents(cui, cuis2nodes)
        return {
            'node_path': cuis2nodes[top_level_parent_node],
            'links': all_links
        }
    except KeyError as e:
        logger.warning(f'Cannot find path concept path:{e}')
        return []
