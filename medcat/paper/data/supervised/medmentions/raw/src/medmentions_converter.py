import os
import json
from typing import Iterator

from medcat.data.mctexport import MedCATTrainerExportDocument, MedCATTrainerExport
from medcat.data.mctexport import MedCATTrainerExportAnnotation
from datetime import datetime


def _unwrap_ann_line(line: str) -> MedCATTrainerExportAnnotation:
    _, start, end, value, type_ids, cui = line.split("\t")
    return {
        "cui": cui,
        "start": start,
        "end": end,
        "value": value,
        "type_ids": type_ids,# EXTRA
    }


def unwrap_anns(ann_lines: list[str]) -> list[MedCATTrainerExportAnnotation]:
    return [
        _unwrap_ann_line(line) for line in ann_lines
    ]


def load_medmentions(file_name: str) -> Iterator[tuple[str, str, str, dict]]:
    with open(file_name) as f:
        all_text = f.read()
    for nr, part in enumerate(all_text.split("\n\n")):
        if not part:
            continue
        # print("PART", nr, ":", type(part), len(part))
        title_line, a_line, *ann_lines = part.split("\n")
        doc_id, title = title_line.split("|t|", 1)
        _doc_id, abstract = a_line.split("|a|", 1)
        assert doc_id == _doc_id
        yield doc_id, title, abstract, unwrap_anns(ann_lines)


def get_export(file_name: str) -> MedCATTrainerExport:
    mct_export: MedCATTrainerExport = {
        "projects": [
            {
                "cuis": "",
                "documents": [],
                "id": file_name,
                "name": file_name,
                "tuis": "",
            }
        ]
    }
    cur_docs: list[MedCATTrainerExportDocument] = []
    for doc_id, doc_title, ann_text, annotations in load_medmentions(file_name):
        doc: MedCATTrainerExportDocument = {
            "text": doc_title + " " + ann_text,
            "annotations": annotations,
            "id": doc_id, 
            "last_modified": datetime.now().isoformat()
        }
        cur_docs.append(doc)
    mct_export['projects'][0]['documents'].extend(cur_docs)
    return mct_export


def save_export(mct_export: dict, file_name: str) -> None:
    if os.path.exists(file_name):
        raise ValueError(f"File exists: {file_name}")
    with open(file_name, 'w') as f:
        json.dump(mct_export, f)


def load_json(fn: str) -> dict:
    with open(fn) as f:
        return json.load(f)


def main(*args: str):
    in_file, out_file = args
    mct_export = get_export(in_file)
    save_export(mct_export, out_file)


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
