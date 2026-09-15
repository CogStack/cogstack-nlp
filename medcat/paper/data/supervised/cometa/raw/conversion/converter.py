from sys import argv
import json
import os.path
from datetime import datetime

from tqdm import tqdm
import pandas as pd

from medcat.data.mctexport import (
    MedCATTrainerExport, MedCATTrainerExportProject,
    MedCATTrainerExportAnnotation)
from medcat.data.mctexport import count_all_docs, count_all_annotations


COLS = ['Term', 'General SNOMED Label', 'General SNOMED ID',
        'Specific SNOMED Label', 'Specific SNOMED ID', 'Example',
        'Example Link', 'Origin_Sheet']
COL4VALUE = "Term"
COL4CUI = "Specific SNOMED ID"
COL4TEXT = "Example"
COL4LINK = "Example Link"

# November 2020
LAST_MODIFIED = datetime(year=2020, month=11, day=1).isoformat()


def find_annotations(value: str, text: str, cui: str
                     ) -> list[MedCATTrainerExportAnnotation]:
    value = value.lower()
    orig_text = text
    text = text.lower()
    if value not in text:
        raise ValueError(f"{repr(value)} not in text ({repr(text)})")
    cur_start = 0
    anns: list[MedCATTrainerExportAnnotation] = []
    while (cur_index := text.find(value, cur_start)) >= 0:
        start = cur_index
        end = cur_index + len(value)
        anns.append(
            {
                "cui": str(cui),
                "value": orig_text[start: end],
                "start": start,
                "end": end,
            }
        )
        cur_start = end
        if len(anns) > 100:
            raise KeyError(
                f"Too many annotations!, {start}, {end}, for {value}. "
                f"cur start at {cur_start}")
    return anns


def do_conversion(df: pd.DataFrame, proj_base_id: str, proj_base_name: str
                  ) -> MedCATTrainerExport:
    projects: list[MedCATTrainerExportProject] = []
    for line_num, (index, line) in enumerate(tqdm(df.iterrows(),
                                                  total=len(df.index))):
        text = line[COL4TEXT]
        cui = line[COL4CUI]
        try:
            anns = find_annotations(
                line[COL4VALUE], text, cui)
        except ValueError as e:
            print("LINE", line_num, "at index", index,
                  "Failed to load(VE):", str(e))
            continue
        except AttributeError as e:
            print("LINE", line_num, "at index", index,
                  "Failed to load(AE):", str(e))
            continue
        proj_id = proj_base_id + str(index)
        proj_name = proj_base_name + "@" + str(index)
        # NOTE: each document is a project so that I can use per-project
        #       filters and thus only focus on the CUI in question and not
        #       the other terms in the text
        projects.append({
            "documents": [
                {
                    "text": text,
                    "annotations": anns,
                    "id": str(index),
                    "name": f"LINK: {line[COL4LINK]}; ID: {index}",
                    "last_modified": LAST_MODIFIED
                }
            ],
            "id": proj_id,
            "name": proj_name,
            "cuis": f'{cui}',
            "tuis": '',
        })
    return {"projects": projects}


def main(file_path: str,
         export_path: str,
         # TODO: options
         ):
    df = pd.read_csv(file_path, sep='\t', index_col=0, header=0).sort_index()
    proj_name = export_path.split(os.path.sep + "cometa" + os.path.sep, 1)[-1]
    proj_id = ".".join(proj_name.split(os.path.sep)[-2:]).replace(".csv", "")
    print("Giving 'project' a name of", repr(proj_name))
    print("And setting ID to", proj_id)
    mct_export = do_conversion(df, proj_id, proj_name)
    print("Got", len(mct_export["projects"]), "projects with a total of",
          count_all_docs(mct_export), "documents and a total of",
          count_all_annotations(mct_export), "annotations")
    print("Saving to", repr(export_path))
    with open(export_path, 'w') as f:
        json.dump(mct_export, f)


if __name__ == "__main__":
    main(*argv[1:])
