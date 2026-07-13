import json

from fastapi.testclient import TestClient

from routellm.main import app


def test_chat_completion_returns_openai_compatible_response() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        headers={
            "X-Request-Id": "client-request-123",
            "X-RouteLLM-Tenant-Id": "sdk-client",
            "X-RouteLLM-Workflow-Id": "chat-sdk",
        },
        json={
            "model": "routellm-auto",
            "messages": [{"role": "user", "content": "Hello from an OpenAI client"}],
            "temperature": 0.2,
            "max_completion_tokens": 64,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "chatcmpl-client-request-123"
    assert data["object"] == "chat.completion"
    assert data["model"] == "local-small"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"]["total_tokens"] == (
        data["usage"]["prompt_tokens"] + data["usage"]["completion_tokens"]
    )
    assert response.headers["X-Request-Id"] == "client-request-123"
    assert response.headers["X-RouteLLM-Selected-Model"] == "local-small"


def test_chat_completion_can_pin_upstream_model_id() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-5-mini",
            "messages": [{"role": "user", "content": "Use the requested model"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["model"] == "gpt-5-mini"
    assert response.headers["X-RouteLLM-Selected-Model"] == "hosted-premium"


def test_chat_completion_unknown_model_uses_openai_error_shape() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "missing-model",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "message": "Unknown model 'missing-model'.",
            "type": "invalid_request_error",
            "param": None,
            "code": "routing_error",
        }
    }


def test_chat_completion_rejects_tools_explicitly() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "routellm-auto",
            "messages": [{"role": "user", "content": "Call a tool"}],
            "tools": [{"type": "function", "function": {"name": "lookup"}}],
        },
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["param"] == "tools"
    assert error["code"] == "unsupported_parameter"


def test_chat_completion_validation_uses_openai_error_shape() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "Missing model"}]},
    )

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request_error"
    assert response.json()["error"]["param"] == "model"


def test_chat_completion_stream_returns_sse_chunks_and_usage() -> None:
    client = TestClient(app)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "routellm-auto",
            "messages": [{"role": "user", "content": "Stream this response"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [line.removeprefix("data: ") for line in response.text.splitlines() if line]
    assert events[-1] == "[DONE]"
    chunks = [json.loads(event) for event in events[:-1]]
    assert chunks[0]["object"] == "chat.completion.chunk"
    assert chunks[0]["choices"][0]["delta"]["role"] == "assistant"
    assert chunks[1]["choices"][0]["delta"]["content"]
    assert chunks[2]["choices"][0]["finish_reason"] == "stop"
    assert chunks[3]["choices"] == []
    assert chunks[3]["usage"]["total_tokens"] > 0
