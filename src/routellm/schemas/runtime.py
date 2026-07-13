from pydantic import BaseModel


class LocalModelReadiness(BaseModel):
    model_key: str
    model_id: str
    installed: bool


class OllamaRuntimeStatus(BaseModel):
    endpoint: str
    reachable: bool
    configured_models: list[LocalModelReadiness]
    detail: str | None = None
