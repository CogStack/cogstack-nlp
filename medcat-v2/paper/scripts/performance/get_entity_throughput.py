from typing import Iterator
import time

import pandas as pd

from medcat.cat import CAT


def get_num_ents_and_time(cat: CAT, text: str) -> tuple[int, float]:
    start_time = time.perf_counter()
    ents = cat.get_entities(text)["entities"]
    spent_time = time.perf_counter() - start_time
    return len(ents), spent_time


def load_data_stream(data_path: str) -> Iterator[str]:
    if data_path.endswith(".csv"):
        df = pd.read_csv(data_path)
        return df['text'].to_list()
    else:
        raise ValueError(f"Unknown data file type: {data_path}")


def get_average_throughput(model_path: str, data_path: str,
                           suppress_output: bool = False):
    if not suppress_output:
        print("Loading model", model_path)
    cat = CAT.load_model_pack(model_path)
    if not suppress_output:
        print("Loading data")
    data = load_data_stream(data_path)
    if not suppress_output:
        print("Running inference")
    throughput = [get_num_ents_and_time(cat, text) for text in data]
    total_time = sum([time for _, time in throughput])
    total_ents = sum([ents for ents, _  in throughput])
    mean_throughput = total_ents / total_time
    return mean_throughput


def main(model_path: str, data_path: str, suppress_output: str = ''):
    throughput = get_average_throughput(
        model_path, data_path, bool(suppress_output))
    print(throughput)


if __name__ == "__main__":
    import sys
    main(*sys.argv[1:])
