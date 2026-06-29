import sys
import os
from typing import Iterator
from datetime import datetime
from functools import lru_cache
import json

import pandas as pd

from medcat.data.mctexport import (
    MedCATTrainerExport, MedCATTrainerExportDocument)
from medcat.data.mctexport import count_all_annotations, count_all_docs


DEFAULT_TEXT_FOLDER = (
    "distemist_zenodo/multilingual_resources/training_text_files/en")
DEFAULT_ANN_FOLDER = (
    "distemist_zenodo/multilingual_resources/en")
DEFAULT_MOD_DATE = datetime.now().isoformat()
DEFAULT_DTYPE = {
    "filename": str,
    "mart": str,
    "label": str,
    "offset1": int,
    "offset2": int,
    "span": str,
    "code": str,
}


def find_text_file(folder: str, base_name: str) -> str:
    path = os.path.join(folder, base_name + ".txt")
    if not os.path.exists(path):
        raise ValueError(f"No such file/folder: {path}")
    return path


def find_text(folder: str, base_name: str) -> str:
    file_path = find_text_file(folder, base_name)
    with open(file_path) as f:
        return f.read()


@lru_cache
def get_doc(folder: str, base_name: str) -> MedCATTrainerExportDocument:
    text = find_text(folder, base_name)
    return {
        "id": hash(base_name),
        "name": base_name,
        "last_modified": DEFAULT_MOD_DATE,
        "text": text,
        "annotations": []
    }


def get_docs(
        annotation_folder: str,
        text_folder: str,
        ) -> Iterator[MedCATTrainerExportDocument]:
    for file_name in os.listdir(annotation_folder):
        print("Looking at annotation file", file_name)
        if not file_name.endswith(".tsv"):
            # print(" - IGNORE")
            continue
        file_path = os.path.join(annotation_folder, file_name)
        df = pd.read_csv(file_path, sep="\t", dtype=DEFAULT_DTYPE,
                         na_values={"code": ""})
        print(" - Read Data", df.index.shape, '\n - And', df.columns)
        for row_nr, row in df.iterrows():
            # print("   - Row nr", row_nr)
            file_base_name = row.filename
            # print("ROW", row)
            # print("CODE", type(row.code), ":", row.code)
            if row.code != row.code:
                print("ROW", row)
                print("CODE", type(row.code), ":", row.code)
                print("Unsuitable! ignoring")
                continue
            cuis = row.code.split("+")
            start, end = row.offset1, row.offset2
            value = row.span
            doc = get_doc(text_folder, file_base_name)
            doc["annotations"].append({
                "id": row_nr,
                "cui": cuis,
                "start": start,
                "end": end,
                "value": value,
                "meta_anns": [],
                "validated": True,
            })
            yield doc


def build_export(text_folder: str, annotation_folder: str
                 ) -> MedCATTrainerExport:
    docs: list[MedCATTrainerExportDocument] = []
    out = {
        "projects": [
            {
                "id": hash("distemist"),
                "name": "distemist",
                "cuis": "",
                "tuis": "",
                "documents": docs
            }
        ]
    }
    for cur_doc in get_docs(annotation_folder, text_folder):
        if cur_doc not in docs:
            # if multuple annotaitons in the same doc/text,
            # we don't want multiple instances
            docs.append(cur_doc)
    return out


def main(text_folder: str, annotation_folder: str,
         target_file: str):
    export = build_export(text_folder, annotation_folder)
    print("Built export w", len(export["projects"]), "projects",
          count_all_docs(export), "docs and", count_all_annotations(export),
          "annotations")
    print("Saving to", target_file)
    with open(target_file, 'w') as f:
        json.dump(export, f)
    print("Done!")


if __name__ == "__main__":
    main(*sys.argv[1:])
