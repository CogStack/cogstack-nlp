from typing import Optional
from multiprocessing import cpu_count
from functools import lru_cache


DEFAULT_SPACY_MODEL = 'en_core_web_md'
DEFAULT_PACK_NAME = "medcat2_model_pack"
COMPONENTS_FOLDER = "saved_components"
AVOID_LEGACY_CONVERSION_ENVIRON = "MEDCAT_AVOID_LECACY_CONVERSION"


@lru_cache(maxsize=100)
def default_weighted_average(step: int, factor: float = 0.0004) -> float:
    return max(0.1, 1 - (step ** 2 * factor))


def workers(workers_override: Optional[int] = None) -> int:
    """Get number of workers.

    Either the number of workers specified (if done so).
    Or the number of workers available (i.e cpu count - 1).

    Args:
        workers_override (Optional[int], optional):
            The number of workers to use. Defaults to None.

    Returns:
        int: _description_
    """
    if workers_override is not None:
        return workers_override
    return max(cpu_count() - 1, 1)


class StatusTypes:
    PRIMARY_STATUS_NO_DISAMB = 'P'
    PRIMARY_STATUS_W_DISAMB = 'PD'
    PRIMARY_STATUS: set[str] = {PRIMARY_STATUS_NO_DISAMB,
                                PRIMARY_STATUS_W_DISAMB}
    MUST_DISAMBIGATE = 'N'
    AUTOMATIC = 'A'
    ALLOWED_STATUS = {PRIMARY_STATUS_NO_DISAMB, MUST_DISAMBIGATE, AUTOMATIC}
    DO_DISAMBUGATION = {MUST_DISAMBIGATE, PRIMARY_STATUS_W_DISAMB}
