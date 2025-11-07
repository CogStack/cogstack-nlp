import logging
import timeit
from contextlib import contextmanager
import cProfile
import pstats
import io


logger = logging.getLogger(__name__)


def _get_stats_str(profile: cProfile.Profile, lines_in_profile: int,
                   stat_type: str) -> str:
    string_io = io.StringIO()
    stats = pstats.Stats(profile, stream=string_io)
    stats.sort_stats(stat_type).print_stats(lines_in_profile)
    return string_io.getvalue()


@contextmanager
def show_profile(do_profiling: bool, lines_in_profile: int):
    if do_profiling:
        profile = cProfile.Profile()

        profile.enable()

    yield

    if do_profiling:
        profile.disable()

        # NOTE: for logging
        tot_stats = _get_stats_str(profile, lines_in_profile, "tottime")
        logger.info("TOTtime for top %d", lines_in_profile)
        logger.info(tot_stats)
        cum_stats = _get_stats_str(profile, lines_in_profile, "cumtime")
        logger.info("CUMtime for top %d", lines_in_profile)
        logger.info(cum_stats)


def perform_work(setup: list[str],
                 worker: list[str],
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
    # do warmup if needed
    for cur_warmup in range(warmup):
        logger.info("Doing warmup step %d", cur_warmup)
        exec("\n".join(setup + worker))
    if startup:
        logger.warning("For startup, will include warmup in timed work")
        worker = setup + worker
        setup = []
    with show_profile(do_profiling=profiling,
                      lines_in_profile=lines_in_profile):
        timed = timeit.repeat(
            "\n".join(worker),
            setup="\n".join(setup),
            repeat=1, number=1
        )
    took_time = timed[0]
    logger.info("Took a total of %ss", took_time)
    # NOTE: print for any time output
    # NOTE: no units for easy automation
    return took_time
