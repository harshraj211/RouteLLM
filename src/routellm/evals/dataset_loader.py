import json
from pathlib import Path

from routellm.schemas.routing import RouteRequest


def load_requests_from_json(path: str | Path) -> list[RouteRequest]:
    dataset_path = Path(path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    return [RouteRequest.model_validate(item) for item in payload]
