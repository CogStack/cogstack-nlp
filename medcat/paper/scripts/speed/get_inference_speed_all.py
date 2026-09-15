import argparse
from pprint import pprint
import json
import os

import get_inference_speed
from common4subproc import do_experiment, RunType, RunConfig


def main():
    parser = argparse.ArgumentParser(
        "get_inference_speed_all"
    )
    parser.add_argument("model_pack_path",
                        help="Model pack path",
                        type=str)
    parser.add_argument("csv_path",
                        help="Path to the csv with (at least a) 'text' field",
                        type=str)
    parser.add_argument("--repeats",
                        help="Number of repeats to use",
                        type=int, default=20)
    parser.add_argument("--save-json", "-j",
                        help="The json path to save the results to",
                        type=str, default=None)
    args = parser.parse_args()
    target_script = os.path.join(
        os.path.dirname(__file__), get_inference_speed.__name__ + ".py")
    results = do_experiment(
        target_script,
        [args.model_pack_path, args.csv_path],
        run_type_map={
            RunType.COLD: ["-w", "0"],
            RunType.WARM: ["-w", "1"],
        },
        cnf=RunConfig(repeats=args.repeats,))
    dumped = {run_type.name: model.model_dump()
              for run_type, model in results.items()}
    if args.save_json:
        print("Saving to", args.save_json)
        with open(args.save_json, 'w') as f:
            json.dump(dumped, f)
    else:
        print("Overall:")
        pprint(dumped)


if __name__ == "__main__":
    main()
