from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    class Config:
        frozen = True

    app_root_path: str = Field(
        default="/", description="The Root Path for the FastAPI App", examples=["/medcat-service"]
    )

    deid_mode: bool = Field(default=False, description="Enable DEID mode")
    deid_redact: bool = Field(
        default=True,
        description="Enable DEID redaction. Returns text like [***] instead of [ANNOTATION]",
    )
