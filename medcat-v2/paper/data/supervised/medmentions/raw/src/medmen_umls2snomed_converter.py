
import json
import os
from copy import deepcopy
from functools import lru_cache
from typing import Callable

import pandas as pd

from medcat.data.mctexport import MedCATTrainerExport, iter_anns, iter_docs
from medcat.data.mctexport import MedCATTrainerExportAnnotation
from medcat.model_creation.preprocess_umls import _DEFAULT_COLUMNS
from medcat.cdb import CDB


UMLS_TYPE_TO_SNOMED_TYPE = {
    "T033": ("67667581", "finding"),
    "T059": ("28321150", "procedure"),
    "T060": ("28321150", "procedure"),
    # "T061": ("28321150", "procedure"),
    "T090": ("16939031", "occupation"),
    "T091": ("16939031", "occupation"),
    "T071": ("2680757", "observable entity"),# and T077/conceptual entity?
    # "" : ("40357424", "foundation metadata concept"),
    # "" : ("29422548", "core metadata concept"),
    "T072": ("32816260", "physical object"),
    # "" : ("7882689", "qualifier value"),
    "T167": ("91187746", "substance"),
    # "" : ("72706784", "nan"),
    "T001": ("81102976", "organism"),
    "T017": ("37552161", "body structure"), # I think?
    "T047": ("9090192", "disorder"),
    # "" : ("33782986", "morphologic abnormality"),
    # "" : ("66527446", "cell structure"),
    "T061": ("47503797", "regime/therapy"),
    # "" : ("91776366", "product"),
    # "" : ("37785117", "medicinal product"),
    "T025": ("99220404", "cell"),
    # "" : ("31601201", "person"),
    # "" : ("20410104", "ethnic group"),
    # "" : ("75168589", "environment"),
    "T051": ("33797723", "event"),
    # "" : ("46922199", "religion/philosophy"),
    "T201": ("43039974", "attribute"),
    # "" : ("3061879", "situation"),
    # "" : ("9593000", "medicinal product form"),
    # "" : ("82417248", "navigational concept"),
    # "" : ("43857361", "physical force"),
    "T200": ("27603525", "clinical drug"),
    # "" : ("13371933", "social concept"),
    # "" : ("30703196", "tumor staging"),
    # "" : ("337250", "specimen"),
    # "" : ("8067332", "basic dose form"),
    # "" : ("21114934", "dose form"),
    # "" : ("55540447", "linkage concept"),
    # "" : ("31685163", "staging scale"),
    # "" : ("90170645", "record artifact"),
    # "" : ("17030977", "assessment scale"),
    # "" : ("25624495", "SNOMED RT+CTV3"),
    # "" : ("18854038", "geographic location"),
    # "" : ("78096516", "environment / location"),
    # "" : ("92873870", "special concept"),
    # "" : ("70426313", "namespace concept"),
    # "" : ("14654508", "racial group"),
    # "" : ("28695783", "link assertion"),
    # "" : ("46506674", "disposition"),
    # "" : ("39041339", "unit of presentation"),
    # "" : ("51885115", "OWL metadata concept"),
    # "" : ("49144999", "state of matter"),
    # "" : ("66203715", "transformation"),
    # "" : ("51120815", "intended site"),
    # "" : ("64755083", "release characteristic"),
    # "" : ("45958968", "administration method"),
    # "" : ("87776218", "role"),
    # "" : ("43744943", "supplier"),
    # "" : ("95475658", "product name"),
    # "" : ("40584095", "metadata"),
    # "" : ("3242456", "life style"),
}

SNOMED_TYPE_ID2NAME = {
    '67667581': 'finding', '28321150': 'procedure', '16939031': 'occupation',
    '2680757': 'observable entity', '40357424': 'foundation metadata concept',
    '29422548': 'core metadata concept', '32816260': 'physical object',
    '7882689': 'qualifier value', '91187746': 'substance', '72706784': 'nan',
    '81102976': 'organism', '37552161': 'body structure', '9090192': 'disorder',
    '33782986': 'morphologic abnormality', '66527446': 'cell structure',
    '47503797': 'regime/therapy', '91776366': 'product', '37785117': 'medicinal product',
    '99220404': 'cell', '31601201': 'person', '20410104': 'ethnic group',
    '75168589': 'environment', '33797723': 'event', '46922199': 'religion/philosophy',
    '43039974': 'attribute', '3061879': 'situation', '9593000': 'medicinal product form',
    '82417248': 'navigational concept', '43857361': 'physical force',
    '27603525': 'clinical drug', '13371933': 'social concept', '30703196': 'tumor staging',
    '337250': 'specimen', '8067332': 'basic dose form', '21114934': 'dose form',
    '55540447': 'linkage concept', '31685163': 'staging scale', '90170645': 'record artifact',
    '17030977': 'assessment scale', '25624495': 'SNOMED RT+CTV3',
    '18854038': 'geographic location', '78096516': 'environment / location',
    '92873870': 'special concept', '70426313': 'namespace concept', '14654508': 'racial group',
    '28695783': 'link assertion', '46506674': 'disposition', '39041339': 'unit of presentation',
    '51885115': 'OWL metadata concept', '49144999': 'state of matter', '66203715': 'transformation',
    '51120815': 'intended site', '64755083': 'release characteristic',
    '45958968': 'administration method', '87776218': 'role', '43744943': 'supplier',
    '95475658': 'product name', '40584095': 'metadata', '3242456': 'life style'
}



def load_export(path: str) -> MedCATTrainerExport:
    with open(path) as f:
        return json.load(f)


def load_umls(umls_path: str) -> pd.DataFrame:
    mrconso = os.path.join(umls_path, "MRCONSO.RRF")
    df = pd.read_csv(mrconso, names=_DEFAULT_COLUMNS, sep="|", index_col=False)
    print("INIT", len(df.index))
    df = df[df["LAT"] == "ENG"]
    print("After LANG", len(df.index))
    df = df[df["SAB"].str.contains("SNOMEDCT")]
    print("After SNOMED", len(df.index))
    df = df[df["SCUI"].notna()]
    print("After removing None-CUIs", len(df.index))
    # remove column I don't care about
    df = df.drop(["LAT",  # language - already selected
                  "LUI",  # unique identifier for term
                  "SUI",  # unique identifier for string
                  "AUI",  # Unique identifier for atom - variable length field, 8 or 9 characters
                  # source stuff - will get CUI from CODE
                  "SAUI",  # Source asserted atom identifier [optional]
                  "SCUI",  # Source asserted concept identifier [optional]
                  "SDUI",  # Source asserted descriptor identifier [optional]
                  ], axis='columns')
    return df


class TPG:

    def __init__(self, pt2ch: dict) -> None:
        self.pt2ch = pt2ch

    @lru_cache
    def get_root_parent(self, cui: str) -> str | None:
        for pt, children in self.pt2ch.items():
            if cui in children:
                rp = self.get_root_parent(pt)
                if rp is None:
                    return cui
        # if not a child of anything, must be root
        return None


def pick_snomed_cui(ann: MedCATTrainerExportAnnotation,
                    umls_df: pd.DataFrame,
                    get_cui_name: Callable[[str], str],
                    tpg: TPG) -> str | None:
    umls_cui = ann['cui']
    snomed_candidates = umls_df[umls_df['CUI'] == umls_cui]
    num_of_candidates = len(snomed_candidates.index)
    if num_of_candidates == 0:
        return None
    elif num_of_candidates == 1:
        return snomed_candidates['CODE'].to_list()[0]
    preferred = snomed_candidates[snomed_candidates["TS"] == "P"]
    num_of_candidates = len(preferred)
    if num_of_candidates == 1 or len(preferred['CODE'].unique()) == 1:
        return preferred['CODE'].to_list()[0]
    return None
    if num_of_candidates == 0:
        # check all if no preferred
        print("No preferred candidates...")
        preferred = snomed_candidates
    cuis_and_names = [(row['CODE'], get_cui_name(row['CODE']))
                      for _, row in preferred.iterrows()
                      if get_cui_name(row['CODE']) != row['CODE'] is not None]
    cuis_with_name = set(cui for cui, _ in cuis_and_names)
    if len(cuis_with_name) == 1:
        return list(cuis_with_name)[0]
    # find one exact match (if present)
    names_of_cuis = set((name, cui) for cui, name in cuis_and_names
                     if name.lower() == ann['value'].lower())
    if len(names_of_cuis) == 1:
        return list(names_of_cuis)[0][1]
    cuitid2 = [
        (cui, name, tid,
         UMLS_TYPE_TO_SNOMED_TYPE[tid],
        #  SNOMED_TYPE_ID2NAME[UMLS_TYPE_TO_SNOMED_TYPE[tid]]
        )
        for cui, name in cuis_and_names
        for tid in ann['type_ids'].split(",")
        if tid in UMLS_TYPE_TO_SNOMED_TYPE]
    print("CUI typeIDs")
    print(cuitid2)
    num_of_candidates = len(preferred)
    print("Picking from", num_of_candidates, 'for', umls_cui, 'from')
    print(preferred)
    print("Context:", ann)
    cand_cuis = [row['CODE'] for _, row in preferred.iterrows()]
    for cui in cand_cuis:
        root = tpg.get_root_parent(cui)  # the type id
        root_name = get_cui_name(root) if root else None
        print("CUI2name", cui, f"({get_cui_name(cui)})",
              "->", root, "->", root_name)
    # import time
    # time.sleep(0.2)


def convert(export: MedCATTrainerExport,
            umls_df: pd.DataFrame,
            cui2name: Callable[[str], str],
            pt2ch: dict) -> MedCATTrainerExport:
    export = deepcopy(export)
    total_initial_anns = len(list(iter_anns(export)))
    tpg = TPG(pt2ch)
    for _, doc, ann in iter_anns(export):
        snomed_cui = pick_snomed_cui(ann, umls_df, cui2name, tpg)
        if snomed_cui:
            ann['cui'] = snomed_cui
        else:
            ann['cui'] = None
    total_kept = 0
    total_removed = 0
    for _, doc in iter_docs(export):
        to_remove = []
        for nr, ann in enumerate(doc['annotations']):
            if ann['cui'] is None:
                to_remove.append(nr)
        total_removed += len(to_remove)
        total_kept += len(doc['annotations']) - len(to_remove)
        # print("Removing", to_remove, "annotations")
        for nr in to_remove[::-1]:
            # start from end to avoid changing order while iterating
            doc["annotations"].pop(nr)
    print("Total removed", total_removed)
    print("Total kept", total_kept)
    print("TOTAL TOTAL", total_removed + total_kept, 'vs', total_initial_anns)
    return export


def main(export_path: str,
         cdb_path: str,
         umls_path: str,
         target_path: str) -> None:
    print("Loading original")
    export = load_export(export_path)
    print("Getting CDB")
    cdb = CDB.load(cdb_path)
    pt2ch = cdb.addl_info['pt2ch']
    print("Loading UMLS")
    umls_df = load_umls(umls_path)
    print("Converting...")
    converted = convert(export, umls_df, cdb.get_name, pt2ch)
    with open(target_path, 'w') as f:
        json.dump(converted, f)


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
