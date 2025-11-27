import json
import time

from cProfile import Profile
from pstats import Stats

from medcat.cat import CAT
from medcat.stats import get_stats

EXAMPLE_DATASET = "paper/data/supervised/cometa/mct_export.json"
EXAMPLE_MODEL_PATH = ".temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"
USE_NEW_LINKER = False
USE_REGEX_TOKENIZER = True
DO_PROFILING = True


def setup_cui_filter(data: dict) -> None:
    per_proj_cuis: list[int] = []
    for proj in data["projects"]:
        all_cuis = {
            ann["cui"]
            for doc in proj["documents"]
            for ann in doc["annotations"]
        }
        cur_cuis = proj["cuis"]
        all_cuis.update(cur_cuis.split(","))
        proj["cuis"] = ",".join(all_cuis)
        per_proj_cuis.append(len(all_cuis))
    print("Total projects", len(per_proj_cuis),
          "\n Min CUIs", min(per_proj_cuis),
          "\n Mean CUIs", sum(per_proj_cuis) / len(per_proj_cuis),
          "\n Max CUIs", max(per_proj_cuis))


def main(
        new_linker_raw: bool | str = USE_NEW_LINKER,
        regex_tokenizer_raw: bool | str = USE_REGEX_TOKENIZER,
        model_path: str = EXAMPLE_MODEL_PATH,
        data_path: str = EXAMPLE_DATASET):
    if isinstance(new_linker_raw, str):
        new_linker = new_linker_raw.lower() in ("new", "yes", "true")
    else:
        new_linker = new_linker_raw
    if isinstance(regex_tokenizer_raw, str):
        regex_tokenizer = regex_tokenizer_raw.lower() in (
            "regex", "yes", "true")
    else:
        regex_tokenizer = regex_tokenizer_raw
    print(f"Setup:\n Linker:{'new' if new_linker else 'old'}"
          f"\n Tokenizer:{'regex' if regex_tokenizer else 'spacy'}")
    print("Loading model", model_path, "...")
    cat = CAT.load_model_pack(model_path)
    # NOTE: prep subnames
    cat.cdb.has_subname("")
    if new_linker:
        print("USING NEW LINKER")
        cat.config.components.linking.comp_name = "primary_name_only_linker"
        cat._recreate_pipe()
    else:
        print("Using DEFAULT linker...")
    if regex_tokenizer:
        print("USING REGEX BASED TOKENIZER")
        cat.config.general.nlp.provider = "regex"
        cat._recreate_pipe()
    else:
        print("Using regular (spacy) tokenizer")
    print("Loading data", data_path)
    with open(data_path) as f:
        data = json.load(f)
    print("setting up CUI filter")
    setup_cui_filter(data)
    print("Running metrics...")
    start = time.perf_counter()
    if DO_PROFILING:
        print("PROFILING")
        profile = Profile()
        profile.enable()
    get_stats(cat, data, use_project_filters=True)
    if DO_PROFILING:
        profile.disable()
    end = time.perf_counter()
    print("Took", end - start)
    if DO_PROFILING:
        print("Profile stats (CUMtime)")
        stats = Stats(profile)
        print(stats.sort_stats("cumtime").print_stats(50))
        print("Profile stats (TOTtime)")
        stats = Stats(profile)
        print(stats.sort_stats("tottime").print_stats(50))


if __name__ == "__main__":
    from sys import argv
    main(*argv[1:])
