import json
import sys
import os
import pandas as pd
import re


VERSION_MODEL_PATTERN = re.compile(r"(v\d)_(.*).json")
FOLDER_NAME_PATTERN = re.compile(r"(.*)_speed")


def extract_test_version_and_model(path: str) -> tuple[str, str, str]:
    dirname = os.path.basename(os.path.dirname(path))
    fnmatch = FOLDER_NAME_PATTERN.match(dirname)
    if not fnmatch:
        raise ValueError(f"Folder name unrecognsied: {dirname}")
    basename = os.path.basename(path)
    match = VERSION_MODEL_PATTERN.match(basename)
    if not match:
        raise ValueError(f"Basename did not match: {basename}")
    return fnmatch.group(1), match.group(1), match.group(2)


def gather_data(json_paths: list[str],
                header=[
                    "Check Type", "Version", "Model", "Warm status",
                    "Mean time", "# of repeats"]
                ) -> pd.DataFrame:
    dfs: list[pd.DataFrame] = []
    for path in json_paths:
        speed_type, version, model = extract_test_version_and_model(path)
        with open(path) as f:
            cur_data = json.load(f)
        print("KEYS", cur_data.keys())
        col1 = list(cur_data.keys())
        mean = [cur_data[cc]['mean'] for cc in col1]
        experiments = [len(cur_data[cc]['all_times']) for cc in col1]
        vals = [speed_type, version, model, col1, mean, experiments]
        dfs.append(pd.DataFrame({col: val for col, val in zip(header, vals)}))
    df = pd.concat(dfs)
    df.sort_values(by=["Check Type", "Model", "Warm status"], inplace=True)
    df.reset_index(inplace=True)
    return df


def main(*file_paths: str):
    df = gather_data(file_paths)
    print(df.to_string())


if __name__ == "__main__":
    main(*sys.argv[1:])
