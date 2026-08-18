import json
import sys
import os
import re

import pandas as pd
from tqdm import tqdm

from common_pref import IS_V2

from medcat.cat import CAT
if IS_V2:
    from medcat.data.mctexport import MedCATTrainerExport, iter_anns
else:
    from medcat.stats.mctexport import MedCATTrainerExport, iter_anns
    from v1_helper import MutableEntity, from_cdb

from my_stats import StatsCalculator


def get_overall_prec_rec_f1(cat: CAT, export: MedCATTrainerExport,
                            filter_before_disamb: bool = False
                            ) -> tuple[float, float, float]:
    if IS_V2:
        calculator = StatsCalculator(
            cat.config.components.linking.filters,
            cat.cdb.cui2info)
        if filter_before_disamb:
            cat.config.components.linking.filter_before_disamb = True
    else:
        calculator = StatsCalculator(
            cat.config.linking.filters,
            from_cdb(cat.cdb))
        if filter_before_disamb:
            cat.config.linking.filter_before_disamb = True
    for proj in tqdm(export["projects"], desc="Projects"):
        if IS_V2:
            calculator.process_project(
                proj, lambda text: cat(text).linked_ents,
                show_progress=False)
        else:
            calculator.process_project(
                proj, lambda text: MutableEntity.from_spacy_list(
                    cat(text).ents),
                show_progress=False)
    overall = calculator.compute_metrics()["overall"]
    return overall["precision"], overall["recall"], overall["f1"]


PREC_REC_F1_PATTERN = re.compile(
    r"Epoch: \d, Prec: (\d\.\d+), Rec: (\d\.\d+), F1: (\d\.\d+)")


def load_data(path: str, setup_filters: bool = True) -> MedCATTrainerExport:
    with open(path) as f:
        data = json.load(f)
    # fix str -> int in some weird exports
    for _, _, ann in iter_anns(data):
        ann["start"] = int(ann["start"])
        ann["end"] = int(ann["end"])
    for proj in data["projects"]:
        all_cuis: set[str] = set()
        for doc in proj["documents"]:
            for ann in doc["annotations"]:
                cuis = ann["cui"]
                if not isinstance(cuis, list):
                    cuis = [cuis, ]
                all_cuis.update(cuis)
        prev_cuis = proj["cuis"]
        if prev_cuis:
            all_cuis.update(proj["cuis"].split(","))
        all_cuis_str = ",".join(all_cuis)
        proj["cuis"] = all_cuis_str
    return data


def main(model_pack_path: str,
         *export_paths: str):
    cat = CAT.load_model_pack(model_pack_path)
    out_data: list[tuple[str, float, float, float, float]] = []
    for export_path in export_paths:
        print("Exploring", export_path)
        data = load_data(export_path)
        new_metrics = get_overall_prec_rec_f1(cat, data)
        out_data.append([os.path.basename(
            os.path.dirname(export_path))] + list(new_metrics))
        print(new_metrics)
    df = pd.DataFrame(
        out_data,
        columns=["filename", "prec", "rec", "F1"]
    )
    print(df.to_string())


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
