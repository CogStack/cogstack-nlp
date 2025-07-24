from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_root_path: str = "/"


class MedcatProcessorSettings(BaseSettings):
    app_log_level: str = "INFO"
    log_level: str = "INFO"

    app_name: str = "MedCAT"
    APP_MODEL_LANGUAGE: str = "en"
    APP_MODEL_NAME: str = "unknown"
    ANNOTATIONS_ENTITY_OUTPUT_MODE: str = "dict"  # assuming it's either "dict" or "list"

    APP_BULK_NPROC: int = 8
    APP_TORCH_THREADS: int = -1

    DEID_MODE: bool = False
    deid_redact: bool = True

    app_training_mode: bool = False
