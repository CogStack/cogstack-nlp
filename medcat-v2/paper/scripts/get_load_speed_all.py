from pydantic import BaseModel, ConfigDict
# import runpy
import subprocess
import os
import sys
import argparse
from pprint import pprint
from enum import Enum, auto
import json

import get_load_speed


class RunConfig(BaseModel):
    repeats: int = 20
    # how many times to perform for warmup
    warmup_count: int = 1


class RunResults(BaseModel):
    all_times: list[float]
    mean: float
    min: float
    max: float

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_times(cls, times: list[float]) -> "RunResults":
        return cls(
            all_times=times,
            mean=sum(times) / len(times),
            min=min(times),
            max=max(times),
        )


class OverallResults(BaseModel):
    startup: RunResults
    cold: RunResults
    warm: RunResults


class RunType(Enum):
    STARTUP = auto()
    COLD = auto()
    WARM = auto()


def _single_experiment(model_path: str,
                       cnf: RunConfig,
                       run_type: RunType,
                       ) -> RunResults:
    target_script = os.path.join(
        os.path.dirname(__file__), get_load_speed.__name__ + ".py")
    sys_argv = [sys.executable, target_script, model_path,]
    if run_type is RunType.STARTUP:
        sys_argv.extend(["-w", "0", "-s"])
    elif run_type is RunType.COLD:
        sys_argv.extend(["-w", "0"])
    elif run_type is RunType.WARM:
        sys_argv.extend(["-w", str(cnf.warmup_count)])
    else:
        raise ValueError("Unknown run type")
    all_took: list[float] = []
    for _ in range(cnf.repeats):
        run_out = subprocess.run(sys_argv, capture_output=True)
        all_took.append(float(run_out.stdout))
    return RunResults.from_times(all_took)


def do_experiment(
        model_path: str,
        cnf: RunConfig = RunConfig(),
        ) -> OverallResults:
    return OverallResults(
        startup=_single_experiment(
            model_path, cnf, RunType.STARTUP),
        cold=_single_experiment(
            model_path, cnf, RunType.COLD),
        warm=_single_experiment(
            model_path, cnf, RunType.WARM)
    )


def main():
    parser = argparse.ArgumentParser(
        "get_load_speed_all"
    )
    parser.add_argument("model_pack_path",
                        help="Model pack path",
                        type=str)
    parser.add_argument("--repeats",
                        help="Number of repeats to use",
                        type=int, default=20)
    parser.add_argument("--save-json", "-j",
                        help="The json path to save the results to",
                        type=float, default=None)
    args = parser.parse_args()
    results = do_experiment(
        args.model_pack_path,
        RunConfig(repeats=args.repeats,))
    dumped = results.model_dump()
    if args.save_json:
        print("Saving to", args.save_json)
        with open(args.save_json, 'w') as f:
            json.dump(dumped, f)
    else:
        print("Overall:")
        pprint(dumped)


if __name__ == "__main__":
    main()
