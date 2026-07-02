from fastapi import FastAPI

from routellm.api.routes import api_router
from routellm.config import get_settings
from routellm.db.setup import create_database
from routellm.observability.tracing import configure_tracing


def create_app() -> FastAPI:
    settings = get_settings()
    create_database()
    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
    )
    configure_tracing(app, settings)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
