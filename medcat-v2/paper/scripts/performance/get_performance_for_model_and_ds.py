import json
import sys
# import io
import os
# from contextlib import contextmanager, redirect_stdout
import re
# from copy import deepcopy
# from collections import Counter

import pandas as pd
from tqdm import tqdm

from common_pref import IS_V2

from medcat.cat import CAT
# from medcat.stats.stats import StatsBuilder, get_stats
if IS_V2:
    from medcat.data.mctexport import MedCATTrainerExport, iter_anns
else:
    from medcat.stats.mctexport import MedCATTrainerExport, iter_anns
    from v1_helper import MutableEntity, from_cdb
# from medcat.data.mctexport import count_all_docs
# from medcat.utils.filters import project_filters

from my_stats import StatsCalculator


def get_overall_prec_rec_f1(cat: CAT, export: MedCATTrainerExport
                            ) -> tuple[float, float, float]:
    if IS_V2:
        calculator = StatsCalculator(
            cat.config.components.linking.filters,
            cat.cdb.cui2info)
    else:
        calculator = StatsCalculator(
            cat.config.linking.filters,
            from_cdb(cat.cdb))
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


# @contextmanager
# def capture_overall_perf():
#     out_perf = []
#     string_io = io.StringIO()
#     with redirect_stdout(string_io):
#         yield out_perf
#     lines = [
#         line for line in
#         string_io.getvalue().split("\n")
#         if line.startswith("Epoch: ")
#     ]
#     f_report_lines = [
#         line for line in
#         string_io.getvalue().split("\n")
#         if line.startswith("FINALISE REPORT w")
#     ]
#     print("\n".join(f_report_lines))
#     if len(lines) != 1:
#         raise ValueError(
#             "Found too many (or too few) matching lines:"
#             f"\n{'\n'.join(lines)}")
#     match = PREC_REC_F1_PATTERN.match(lines[0])
#     if not match:
#         raise ValueError(f"Did not match pattern:\n{lines[0]}")
#     out_perf.append((
#         float(match.group(1)), float(match.group(2)), float(match.group(3))))


def load_data(path: str, setup_filters: bool = True) -> MedCATTrainerExport:
    with open(path) as f:
        data = json.load(f)
    # fix str -> int in some weird exports
    for _, _, ann in iter_anns(data):
        ann["start"] = int(ann["start"])
        ann["end"] = int(ann["end"])
    # # count how many extras we did created
    # fixer: dict[str, int] = Counter()
    # for _, doc in iter_docs(data):
    #     do_rearrange = False
    #     for ann in list(doc["annotations"]):
    #         if isinstance(ann["cui"], list):
    #             do_rearrange = True
    #             doc["annotations"].remove(ann)
    #             for cui in ann["cui"]:
    #                 cp_ann = deepcopy(ann)
    #                 cp_ann["cui"] = cui
    #                 doc["annotations"].append(ann)
    #                 fixer[cui] += 1
    #     if do_rearrange:
    #         doc["annotations"].sort(key=lambda ann: ann["start"])
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


# def get_stats(cat: CAT, data: MedCATTrainerExport,
#               fixer: dict[str, int]):
#     builder = StatsBuilder.from_cat(cat,
#                                     use_project_filters=True,
#                                     use_overlaps=True)
#     for pind, project in tqdm(enumerate(data['projects']),
#                               desc="Stats project",
#                               total=len(data['projects']),
#                               leave=False):
#         with project_filters(cat.config.components.linking.filters,
#                              project,
#                              builder.extra_cui_filter,
#                              builder.use_project_filters):
#             builder.process_project(project)
#     # TODO: how do I use the fixer?
#     # this is the part that prints out the stats
#     builder.finalise_report(0, do_print=True)


def main(model_pack_path: str,
         *export_paths: str):
    cat = CAT.load_model_pack(model_pack_path)
    out_data: list[tuple[str, float, float, float, float]] = []
    for export_path in export_paths:
        print("Exploring", export_path)
        data = load_data(export_path)
        # with capture_overall_perf() as captured:
        #     get_stats(cat, data)
        # out_data.extend([os.path.basename(export_path)] + captured)
        # print("GOT", captured)
        # print("NEW VERSION")
        new_metrics = get_overall_prec_rec_f1(cat, data)
        out_data.extend([os.path.basename(export_path)] + list(new_metrics))
        print(new_metrics)
    df = pd.DataFrame(
        out_data,
        columns=["filename", "prec", "rec", "F1"]
    )
    print(df.to_string())


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
