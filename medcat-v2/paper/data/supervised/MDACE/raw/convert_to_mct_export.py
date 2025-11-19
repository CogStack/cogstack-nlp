import json
import os
import sys
from datetime import datetime
from typing import Iterator

from medcat.data.mctexport import (
    MedCATTrainerExport, MedCATTrainerExportProject,
    MedCATTrainerExportDocument, MedCATTrainerExportAnnotation)
from medcat.data.mctexport import count_all_annotations, count_all_docs

DEFAULT_INPUT_DIR = "with_text/gold"
DEFAULT_OUTPUT_PATH = "../icd10_convert.json"


def get_all_jsons(input_dir: str) -> Iterator[str]:
    for fn in os.listdir(input_dir):
        path = os.path.join(input_dir, fn)
        if os.path.isdir(path):
            yield from get_all_jsons(path)
        elif path.endswith(".json"):
            yield path


def do_conversion(
        input_dir: str = DEFAULT_INPUT_DIR,
        output_file: str = DEFAULT_OUTPUT_PATH):
    mod_time = datetime.now().isoformat()
    all_out: MedCATTrainerExport = {
        "projects": []
    }

    for path in get_all_jsons(input_dir):
        if not path.endswith(".json"):
            continue
        with open(path) as f:
            in_data = json.load(f)
        documents: list[MedCATTrainerExportDocument] = []
        proj_id = in_data["hadm_id"]
        proj_name = f'MDACE_{proj_id}'
        project: MedCATTrainerExportProject = {
            "documents": documents,
            "name": proj_name,
            "id": proj_id,
            "cuis": "",
            "tuis": "",
        }
        all_out["projects"].append(project)

        in_notes = in_data["notes"]  # guess name
        for in_doc in in_notes:
            doc_id = in_doc["note_id"]
            doc_name = f'{in_doc["description"]}_{doc_id}'
            anns: list[MedCATTrainerExportAnnotation] = []
            documents.append(
                {
                    "name": doc_name,
                    "id": doc_id,
                    "last_modified": mod_time,
                    "text": in_doc["text"],
                    "annotations": anns,
                }
            )

            for ann_num, ann in enumerate(in_doc["annotations"]):
                anns.append(
                    {
                        "start": ann["begin"],
                        "end": ann["end"],
                        # NOTE: this is currently in ICD
                        "cui": ann["code"],
                        "value": ann["covered_text"],
                        "id": f"{proj_name}_{doc_name}_{ann_num}",
                        "meta_anns": [],
                        "validated": True,
                    }
                )
    print("GOT", len(all_out["projects"]), "projects",
          "with", count_all_annotations(all_out), "annotations",
          "across", count_all_docs(all_out), "documents")

    with open(output_file, "w") as of:
        json.dump(all_out, of, indent=2)


if __name__ == "__main__":
    do_conversion(*sys.argv[1:])
