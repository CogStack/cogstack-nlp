
import time
import cProfile
import pstats
import argparse
import logging
import io
OVERALL_START_TIME = time.perf_counter()
from medcat.cat import CAT  # noqa


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
        args.model_pack_path,
        warmup=args.warmup,
        startup=args.startup,
        verbose=args.verbose,
        profiling=args.do_profiling,
        lines_in_profile=args.num_in_profile
    )
    print(took_time)
    return took_time


def perform_work(model_pack_path: str,
                 warmup: int,
                 startup: bool,
                 verbose: bool,
                 profiling: bool,
                 lines_in_profile: int,
                 ) -> float:
    sh = logging.StreamHandler()
    logger.addHandler(sh)
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.CRITICAL)
    # NOTE: to make sure all the imports are done and so on
    if warmup > 0 and startup:
        raise ValueError("Timing warmed up from startup doesn't make sense")
    logger.debug("Starting with wramp of %d repetations", warmup)
    for cur_warmup in range(warmup):
        logger.debug("Warmup number %d ...", cur_warmup)
        load_once(model_pack_path, False, 0)
    logger.info("Warmup done! Now loading!")
    # NOTE: if doing startup, then counting from before
    if startup:
        logger.info("Using overall start time (before import)")
    start_time = time.perf_counter() if not startup else OVERALL_START_TIME
    load_once(model_pack_path, profiling, lines_in_profile)
    took_time = time.perf_counter() - start_time
    logger.info("Took a total of %ss", took_time)
    # NOTE: print for any time output
    # NOTE: no units for easy automation
    return took_time


def _get_stats_str(profile: cProfile.Profile, lines_in_profile: int,
                   stat_type: str) -> str:
    string_io = io.StringIO()
    stats = pstats.Stats(profile, stream=string_io)
    stats.sort_stats(stat_type).print_stats(lines_in_profile)
    return string_io.getvalue()


def load_once(model_path: str, do_profiling: bool,
              lines_in_profile: int):
    if do_profiling:
        profile = cProfile.Profile()

        profile.enable()

    CAT.load_model_pack(model_path)

    if do_profiling:
        profile.disable()

        # NOTE: for logging
        tot_stats = _get_stats_str(profile, lines_in_profile, "tottime")
        logger.info("TOTtime for top %d", lines_in_profile)
        logger.info(tot_stats)
        cum_stats = _get_stats_str(profile, lines_in_profile, "cumtime")
        logger.info("CUMtime for top %d", lines_in_profile)
        logger.info(cum_stats)


if __name__ == "__main__":
    took_time = main()
