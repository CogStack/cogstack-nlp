import sys
import json
from collections import defaultdict

from medcat.cat import CAT
from medcat.data.mctexport import (
    MedCATTrainerExport, MedCATTrainerExportAnnotation,
    count_all_annotations, count_all_docs)


def load_export(path: str) -> MedCATTrainerExport:
    with open(path) as f:
        return json.load(f)


def icd2snomed(cat: CAT) -> dict[str, list[str]]:
    code2snomed: dict[str, list[str]] = defaultdict(list)
    cui2icd10 = cat.cdb.addl_info["cui2icd10"]
    for cui_info in cat.cdb.cui2info.values():
        cui = cui_info["cui"]
        for icd10 in cui2icd10.get(cui, []):
            code2snomed[icd10].append(cui)
    print("GOT", len(code2snomed), "ICD codes")
    print("Mapped to", sum(len(v) for v in code2snomed.values()),
          "total Snomed CUIs")
    return code2snomed


def pick_concept(cat: CAT,
                 mapper: dict[str, list[str]],
                 ann: MedCATTrainerExportAnnotation) -> str | None:
    # NOTE: I could try and select 1 - the best
    #       but there isn't really a good way to do that.
    #       Instead, we'll use all as candidates
    return mapper.get(ann["cui"])


def convert_export(
        cat: CAT, export: MedCATTrainerExport
        ) -> MedCATTrainerExport:
    mapper = icd2snomed(cat)
    return {
        "projects": [
            {
                "id": proj["id"],
                "name": proj["name"],
                "cuis": proj["cuis"],
                "tuis": proj["tuis"],
                "documents": docs
            }
            for proj in export["projects"]
            if (docs := [
                {
                    "id": doc["id"],
                    "name": doc["name"],
                    "last_modified": doc["last_modified"],
                    "text": doc["text"],
                    "annotations": anns
                } for doc in proj["documents"]
                if (anns := [
                    {
                        "id": ann["id"],
                        "start": ann["start"],
                        "end": ann["end"],
                        "value": ann["value"],
                        "cui": mapped_cui,
                        "meta_anns": ann["meta_anns"],
                        "validated": ann["validated"]
                    } for ann in doc["annotations"]
                    if (mapped_cui := pick_concept(cat, mapper, ann))
                    ])
            ])
        ]
    }


def main(model_pack_path: str,
         icd10_export_path: str,
         final_export_path: str):
    print("Loading model pack", model_pack_path)
    cat = CAT.load_model_pack(model_pack_path)
    print("Loading export")
    export = load_export(icd10_export_path)
    print("Initial import has", count_all_docs(export), "docs",
          "and", count_all_annotations(export), "anns within",
          len(export["projects"]), "projects")
    print("Converting...")
    converted = convert_export(cat, export)
    print("CONVERTED export HAS", count_all_docs(converted), "docs",
          "and", count_all_annotations(converted), "anns within",
          len(converted["projects"]), "projects")
    from medcat.data.mctexport import iter_anns
    lens = []
    for _, _, ann in iter_anns(converted):
        lens.append(len(ann["cui"]) if isinstance(ann["cui"], list) else 1)
    print("Total", len(lens), "annotations with", sum(lens) / len(lens),
          "values on average")
    print("Saving to", final_export_path)
    with open(final_export_path, 'w') as f:
        json.dump(converted, f)


if __name__ == "__main__":
    main(*sys.argv[1:])
