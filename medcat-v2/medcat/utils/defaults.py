import os
from typing import Optional
from multiprocessing import cpu_count
from functools import lru_cache
import logging


DEFAULT_SPACY_MODEL = 'en_core_web_md'
DEFAULT_PACK_NAME = "medcat2_model_pack"
COMPONENTS_FOLDER = "saved_components"
AVOID_LEGACY_CONVERSION_ENVIRON = "MEDCAT_AVOID_LECACY_CONVERSION"


def avoid_legacy_conversion() -> bool:
    return os.environ.get(
        AVOID_LEGACY_CONVERSION_ENVIRON, "False").lower() == "true"


class LegacyConversionDisabledError(Exception):
    """Raised when legacy conversion is disabled."""

    def __init__(self, component_name: str):
        super().__init__(
            f"Legacy conversion is disabled (while loading {component_name}). "
            f"Set the environment variable {AVOID_LEGACY_CONVERSION_ENVIRON} "
            "to `False` to allow conversion.")


def doing_legacy_conversion_message(
        logger: logging.Logger, component_name: str, file_path: str = '',
        level: int = logging.WARNING
        ) -> None:
    logger.log(
        level,
        "Doing legacy conversion on %s (at '%s'). "
        "Set the environment variable %s "
        "to `True` to avoid this.",
        component_name, file_path, AVOID_LEGACY_CONVERSION_ENVIRON)


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
