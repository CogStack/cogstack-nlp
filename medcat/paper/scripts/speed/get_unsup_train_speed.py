from common import perform_work, mct_ver
from pydantic import BaseModel
import argparse


class InferenceSpeedConfig(BaseModel):
    model_pack_path: str
    inference_file_path: str


def main():
    parser = argparse.ArgumentParser(
        "get_inference_speed.py"
    )
    parser.add_argument("model_pack_path",
                        help="The path to the model pack",
                        type=str)
    parser.add_argument("csv_path",
                        help="Path to the csv with (at least a) 'text' field",
                        type=str)
    parser.add_argument("--verbose", "-v",
                        help="Whether to run in verbose mode",
                        action="store_true")
    parser.add_argument("--do-profiling", "-p",
                        help="Whether to run profiling on top of just timing",
                        action="store_true")
    parser.add_argument("--num-in-profile", "--np",
                        help="The number of lines in the profile.",
                        type=int, default=20)
    parser.add_argument("--startup", "-s",
                        help="Whether to use the startup as the start time. "
                        "This is useful when trying to include import times "
                        "as well - i.e real user experience",
                        action="store_true")
    parser.add_argument("--warmup", "-w",
                        help="The number of warmup rounds",
                        type=int, default=1)
    args = parser.parse_args()
    if mct_ver.startswith("1."):
        work_string = "cat.train(df.text)"
    elif mct_ver.startswith("2."):
        work_string = "cat.trainer.train_unsupervised(df.text)"
    took_time = perform_work(
        setup=["from medcat.cat import CAT",
               "import pandas as pd",
               f"cat = CAT.load_model_pack('{args.model_pack_path}')",
               # NOTE: this reset subnames - it is only required for models saved
               #       in v2 pre-beta releases
               "cat.cdb.has_subname('abc')" if mct_ver.startswith("2") else "",
               f"df = pd.read_csv('{args.csv_path}')"],
        worker=[work_string],
        warmup=args.warmup,
        startup=args.startup,
        verbose=args.verbose,
        profiling=args.do_profiling,
        lines_in_profile=args.num_in_profile
    )
    print(took_time)
    return took_time


if __name__ == "__main__":
    main()
