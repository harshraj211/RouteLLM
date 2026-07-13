from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

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

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> Response:
        if request.url.path == f"{settings.api_prefix}/chat/completions":
            first_error = exc.errors()[0]
            location = first_error.get("loc", ())
            param = str(location[-1]) if location else None
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": first_error.get("msg", "Invalid request."),
                        "type": "invalid_request_error",
                        "param": param,
                        "code": "invalid_parameter",
                    }
                },
            )
        return await request_validation_exception_handler(request, exc)

    return app


app = create_app()
