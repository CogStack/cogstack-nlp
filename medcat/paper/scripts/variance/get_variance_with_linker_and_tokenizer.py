import json
import time
from enum import Enum
import io
from contextlib import redirect_stdout, redirect_stderr, contextmanager
import re
import os

from cProfile import Profile
from pstats import Stats

from medcat.cat import CAT
from medcat.components.types import CoreComponentType
from medcat.stats import get_stats

EXAMPLE_DATASET = "paper/data/supervised/cometa/mct_export.json"
EXAMPLE_MODEL_PATH = ".temp/CONVERT_2023_model_no_mc_234dda1597f635e3.zip"
USE_LINKER = "DEFAULT"
USE_REGEX_TOKENIZER = True
DO_PROFILING = False


class LinkerType(Enum):
    DEFAULT = 0
    VECTOR_CONTEXT = 0
    FASTER = 1
    EMBEDDING = 2

    @classmethod
    def get_type(cls, linker: str) -> 'LinkerType':
        if linker.upper() in cls:
            return cls[linker.upper()]
        elif linker.lower() in ("new", "faster"):
            return cls.FASTER
        elif "embed" in linker.lower():
            return cls.EMBEDDING
        elif linker.lower() in ("normal", "def", "regular", "reg", "old"):
            return cls.DEFAULT
        raise ValueError(f"Unknown linker type: '{linker}'")

    def set_linker(self, cat: CAT):
        cmp_cnf = cat.config.components
        if self is LinkerType.DEFAULT:
            # make change just in case this is a re-run / subsequent change
            cmp_cnf.linking.comp_name = "default"
        if self is LinkerType.FASTER:
            cmp_cnf.linking.comp_name = "primary_name_only_linker"
        elif self is LinkerType.EMBEDDING:
            from medcat.config.config import EmbeddingLinking
            from medcat.components.linking.embedding_linker import (
                Linker as ELinker)
            cmp_cnf.linking = EmbeddingLinking()
            # NOTE: should fix on the lib side
            cmp_cnf.linking.comp_name = "medcat2_embedding_linker"
            # need to recreate and create embeddings
            cat._recreate_pipe()
            linker: ELinker = cat.pipe.get_component(CoreComponentType.linking)
            print("Creating embeddings...")
            linker.create_embeddings()
            # NOTE: returning without another pipe recreation
            return
        else:
            raise ValueError("Not defined for linker:")
        cat._recreate_pipe()


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


@contextmanager
def capture_output():
    f = io.StringIO()
    out_list = []
    with redirect_stdout(f):
        with redirect_stderr(f):
            yield out_list
    lines = f.getvalue().split("\n")
    linker: str | None = None
    tokenizer: str | None = None
    prec: str | None = None
    rec: str | None = None
    f1: str | None = None
    time_taken: str | None = None
    ent_throughput: str | None = None
    for line in lines:
        if m := re.match(r"\s+Linker:\s*(.*)", line):
            linker = m.group(1)
        elif m := re.match(r"\s+Tokenizer:\s*(.*)", line):
            tokenizer = m.group(1)
        elif m := re.search(
                r"Epoch:\s*0,.*Prec:\s*([\d.]+),\s*"
                r"Rec:\s*([\d.]+),\s*"r"F1:\s*([\d.]+)", line):
            prec, rec, f1 = m.groups()
        elif m := re.search(
                r"Took ([\d.]+)", line):
            time_taken = m.group(1)
        elif m:= re.search(
                r"Throughput rate (\d+\.\d+)", line):
            ent_throughput = m.group(1)
        if None not in (linker, tokenizer, prec, rec, f1, time_taken, ent_throughput):
            # break early if all found
            break
    if None in (linker, tokenizer, prec, rec, f1, time_taken, ent_throughput):
        raise ValueError(
            "Unable to find linker, tokenizer, precision, recall, f1, ent_throughput"
            "or time taken. Got "
            f"{linker}, {tokenizer}, {prec}, {rec}, {f1}, {time_taken}, {ent_throughput}")
    out_list.extend([linker, tokenizer, prec, rec, f1, time_taken, ent_throughput])


def main(
        linker_type_str: str = USE_LINKER,
        regex_tokenizer_raw: bool | str = USE_REGEX_TOKENIZER,
        model_path: str = EXAMPLE_MODEL_PATH,
        data_path: str = EXAMPLE_DATASET,
        one_line_only: bool = False):
    if one_line_only:
        with capture_output() as captured:
            _main(linker_type_str, regex_tokenizer_raw,
                  model_path, data_path)
        # start with data path
        data_folder_name = os.path.basename(
            os.path.dirname(data_path))
        print(",".join([data_folder_name] + captured))
    else:
        _main(linker_type_str, regex_tokenizer_raw,
              model_path, data_path)


def _main(
        linker_type_str: str = USE_LINKER,
        regex_tokenizer_raw: bool | str = USE_REGEX_TOKENIZER,
        model_path: str = EXAMPLE_MODEL_PATH,
        data_path: str = EXAMPLE_DATASET):
    linker_type = LinkerType.get_type(linker_type_str)
    if isinstance(regex_tokenizer_raw, str):
        regex_tokenizer = regex_tokenizer_raw.lower() in (
            "regex", "yes", "true")
    else:
        regex_tokenizer = regex_tokenizer_raw
    print(f"Setup:\n Linker:{linker_type.name}"
          f"\n Tokenizer:{'regex' if regex_tokenizer else 'spacy'}")
    print("Loading model", model_path, "...")
    cat = CAT.load_model_pack(model_path)
    # NOTE: prep subnames
    cat.cdb.has_subname("")
    if linker_type != LinkerType.DEFAULT:
        print("USING non-default LINKER", linker_type)
        linker_type.set_linker(cat)
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
    fps, _, tps, *_ = get_stats(cat, data, use_project_filters=True)
    if DO_PROFILING:
        profile.disable()
    end = time.perf_counter()
    time_taken = end - start
    print("Took", time_taken)
    ents_found = sum(fps.values()) + sum(tps.values())
    print("Throughput rate", ents_found / time_taken)
    if DO_PROFILING:
        print("Profile stats (CUMtime)")
        stats = Stats(profile)
        print(stats.sort_stats("cumtime").print_stats(50))
        print("Profile stats (TOTtime)")
        stats = Stats(profile)
        print(stats.sort_stats("tottime").print_stats(50))


if __name__ == "__main__":
    from sys import argv
    one_line_only = "--one-line" in argv
    if one_line_only:
        argv.remove("--one-line")
    main(*argv[1:], one_line_only=one_line_only)
