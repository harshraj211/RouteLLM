from routellm.config import Settings


def test_settings_accept_standard_openai_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")

    settings = Settings(_env_file=None)

    assert settings.hosted_api_key is not None
    assert settings.hosted_api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)
