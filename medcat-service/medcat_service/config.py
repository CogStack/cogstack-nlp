from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_root_path: str = Field("/", description="The Root Path for the FastAPI App", examples=["/medcat-service"])
