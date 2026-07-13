from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=False)


class Settings(BaseSettings):
    app_name: str = "RouteLLM"
    environment: str = Field(default="development")
    api_prefix: str = "/v1"
    default_currency: str = "USD"
    database_url: str = "sqlite:///./routellm.db"
    redis_url: str = "redis://localhost:6379/0"
    enable_docs: bool = True
    inference_mode: Literal["mock", "live"] = "mock"
    inference_timeout_seconds: float = 30.0
    inference_max_retries: int = Field(default=1, ge=0, le=5)
    inference_retry_backoff_seconds: float = Field(default=0.1, ge=0.0, le=10.0)
    chat_default_tenant_id: str = "default"
    chat_default_workflow_id: str = "chat-completions"
    chat_default_task_type: str = "qa"
    chat_default_max_budget_usd: float = Field(default=0.05, gt=0)
    chat_default_latency_slo_ms: int = Field(default=30000, gt=0)
    analytics_baseline_model_key: str = "hosted-premium"
    model_registry_path: Path = Path("config/models.yaml")
    model_registry_writes_enabled: bool = True
    local_small_base_url: str = "http://localhost:8001/v1"
    local_small_model: str = "local-small"
    local_medium_base_url: str = "http://localhost:8002/v1"
    local_medium_model: str = "local-medium-json"
    hosted_base_url: str = "https://api.openai.com/v1"
    hosted_model: str = "gpt-5-mini"
    hosted_api_key_env: str = "OPENAI_API_KEY"
    hosted_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ROUTELLM_HOSTED_API_KEY", "OPENAI_API_KEY"),
    )
    otel_enabled: bool = False
    otel_service_name: str = "routellm-api"
    otel_exporter_otlp_endpoint: str | None = None

    model_config = SettingsConfigDict(
        env_prefix="ROUTELLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
