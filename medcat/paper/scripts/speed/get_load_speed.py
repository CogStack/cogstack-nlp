import argparse
import logging

from common import perform_work


logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        "get_load_speed.py"
    )
    parser.add_argument("model_pack_path",
                        help="model_pack_path",
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
    took_time = perform_work(
        setup=["from medcat.cat import CAT",],
        worker=[f"""CAT.load_model_pack("{args.model_pack_path}")"""],
        warmup=args.warmup,
        startup=args.startup,
        verbose=args.verbose,
        profiling=args.do_profiling,
        lines_in_profile=args.num_in_profile
    )
    print(took_time)
    return took_time


if __name__ == "__main__":
    took_time = main()
