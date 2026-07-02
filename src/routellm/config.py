from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RouteLLM"
    environment: str = Field(default="development")
    api_prefix: str = "/v1"
    default_currency: str = "USD"
    database_url: str = "sqlite:///./routellm.db"
    redis_url: str = "redis://localhost:6379/0"
    enable_docs: bool = True

    model_config = SettingsConfigDict(env_prefix="ROUTELLM_", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
