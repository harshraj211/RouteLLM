from routellm.config import Settings


def test_settings_accept_standard_openai_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")

    settings = Settings(_env_file=None)

    assert settings.hosted_api_key is not None
    assert settings.hosted_api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)


def test_ollama_timeout_defaults_to_a_longer_local_inference_window(monkeypatch) -> None:
    monkeypatch.delenv("ROUTELLM_INFERENCE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("ROUTELLM_OLLAMA_INFERENCE_TIMEOUT_SECONDS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.inference_timeout_seconds == 30.0
    assert settings.ollama_inference_timeout_seconds == 300.0
