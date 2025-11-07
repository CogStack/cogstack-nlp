import sys
from enum import Enum, auto
from pydantic import BaseModel, ConfigDict
import subprocess


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


def _single_experiment(target_script: str,
                       target_args: list[str],
                       cnf: RunConfig,
                       run_type: RunType,
                       run_type_map: dict[RunType, list[str]],
                       ) -> RunResults:
    sys_argv = [sys.executable, target_script,] + target_args
    if run_type in run_type_map:
        sys_argv += run_type_map[run_type]
    all_took: list[float] = []
    for _ in range(cnf.repeats):
        run_out = subprocess.run(sys_argv, capture_output=True)
        try:
            took_time = float(run_out.stdout)
        except ValueError as err:
            raise ValueError(
                f"Unable to get run time from for {run_type}:\n"
                f"'{run_out.stdout.decode()}'\n"
                f"\nError output was:\n"
                f"{run_out.stderr.decode()}\n"
                f"\nWas running the command:\n {' '.join(sys_argv)}"
                ) from err
        all_took.append(took_time)
    return RunResults.from_times(all_took)


def do_experiment(
        target_script: str,
        target_args: list[str],
        run_type_map: dict[RunType, list[str]],
        cnf: RunConfig = RunConfig(),
        ) -> OverallResults:
    return OverallResults(
        startup=_single_experiment(
            target_script, target_args, cnf, RunType.STARTUP,
            run_type_map=run_type_map),
        cold=_single_experiment(
            target_script, target_args, cnf, RunType.COLD,
            run_type_map=run_type_map),
        warm=_single_experiment(
            target_script, target_args, cnf, RunType.WARM,
            run_type_map=run_type_map)
    )
