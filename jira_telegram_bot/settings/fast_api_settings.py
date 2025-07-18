from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from pydantic import Field
class FastAPISettings(BaseSettings):
    port: int = Field(default=6602)
    host: str = Field(default="0.0.0.0")
    log_level: str = Field(default="info")
    workers: int = Field(default=1)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="fastapi_",
        extra="ignore",
    )
