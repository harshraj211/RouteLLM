from routellm.main import create_app


def test_app_boots_without_tracing_enabled() -> None:
    app = create_app()
    assert app.title == "RouteLLM"
