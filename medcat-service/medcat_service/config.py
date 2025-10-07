import logging
from typing import Any, Optional, Tuple, Union

import torch
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _coerce_loglevel(v: Any) -> int:
    """
    Accept int or common strings like 'INFO', 'debug', etc.
    """
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        name = v.strip().upper()
        # Map name to logging level; default INFO if unknown
        return getattr(logging, name, logging.INFO)
    return logging.INFO


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        frozen=True,
        env_prefix="",  # no prefix; we specify full env names via alias
        case_sensitive=False,
        populate_by_name=True
    )

    app_root_path: str = Field(
        default="/",
        description="The Root Path for the FastAPI App",
        examples=["/medcat-service"],
    )

    deid_mode: bool = Field(default=False,
                            validation_alias=AliasChoices("deid_mode", "MEDCAT_DEID_MODE"),
                            description="Enable DEID mode"
                            )
    deid_redact: bool = Field(
        default=True,
        validation_alias=AliasChoices("deid_redact", "MEDCAT_DEID_REDACT"),
        description="Enable DEID redaction. Returns text like [***] instead of [ANNOTATION]"
    )

    # Model paths
    model_cdb_path: Optional[str] = Field("/cat/models/medmen/cdb.dat", alias="APP_MODEL_CDB_PATH")
    model_vocab_path: Optional[str] = Field("/cat/models/medmen/vocab.dat", alias="APP_MODEL_VOCAB_PATH")
    model_meta_path_list: Union[str, Tuple[str, ...]] = Field(default=(), alias="APP_MODEL_META_PATH_LIST")
    model_rel_path_list: Union[str, Tuple[str, ...]] = Field(default=(), alias="APP_MODEL_REL_PATH_LIST")
    medcat_model_pack: Optional[str] = Field("", alias="APP_MEDCAT_MODEL_PACK")
    model_cui_filter_path: Optional[str] = Field("", alias="APP_MODEL_CUI_FILTER_PATH")
    spacy_model: str = Field("", alias="MEDCAT_SPACY_MODEL")

    # ---- App logging & MedCAT logging ----
    app_log_level: int = Field(default=logging.INFO, alias="APP_LOG_LEVEL")
    medcat_log_level: int = Field(default=logging.INFO, alias="MEDCAT_LOG_LEVEL")

    # ---- App identity / model basics ----
    app_name: str = Field(default="MedCAT", alias="APP_NAME")
    app_model_language: str = Field(default="en", alias="APP_MODEL_LANGUAGE")
    app_model_name: str = Field(default="unknown", alias="APP_MODEL_NAME")

    # ---- Performance knobs ----
    bulk_nproc: int = Field(8, alias="APP_BULK_NPROC")
    torch_threads: int = Field(-1, alias="APP_TORCH_THREADS")

    # ---- Output formatting ----
    # e.g. "dict" | "list" | "json" (service currently uses "dict" default)
    annotations_entity_output_mode: str = Field(default="dict", alias="MEDCAT_ANNOTATIONS_ENTITY_OUTPUT_MODE")

    # ---- Normalizers ---------------------------------------------------------
    @field_validator("app_log_level", "medcat_log_level", mode="before")
    @classmethod
    def _val_log_levels(cls, v: Any) -> int:
        return _coerce_loglevel(v)

    @field_validator("annotations_entity_output_mode", mode="after")
    @classmethod
    def _lower_mode(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("model_meta_path_list", "model_rel_path_list", mode="before")
    @classmethod
    def _split_paths(cls, v):
        if not v:
            return ()
        if isinstance(v, str):
            return tuple(p.strip() for p in v.split(":") if p.strip())
        if isinstance(v, (list, tuple)):
            return tuple(v)
        return ()

    @classmethod
    def env_name(cls, field: str) -> str:
        """Return the env var name (alias) for a given field name."""
        return cls.model_fields[field].alias or field

    @field_validator("bulk_nproc", mode="before")
    def adjust_bulk_nproc(cls, num_procs: int) -> int:
        """ This method is used to adjust the number of processes to use for bulk processing.
            Set number of processes to 1 if MPS (Apple Sillicon) is available, as MPS does not support multiprocessing.

        Args:
            num_procs (int): number of processes requested

        Returns:
            int: number of processes to use
        """
        if torch.backends.mps.is_available():
            return 1
        return num_procs
