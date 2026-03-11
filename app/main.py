from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.middleware.auth import AuthMiddleware
from app.api.middleware.logging import LoggingMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.routes import execute, health
from app.core.config import settings
from app.core.constants import APIConstants
from app.core.exceptions import AppException
from app.core.utils import utc_now_iso
from app.infrastructure.logging.logger import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(LoggingMiddleware)

    app.include_router(health.router, prefix=APIConstants.V1_PREFIX, tags=["health"])
    app.include_router(execute.router, prefix=APIConstants.V1_PREFIX, tags=["execute"])

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        trace_id = getattr(request.state, "trace_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "trace_id": trace_id,
                "timestamp": utc_now_iso(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        trace_id = getattr(request.state, "trace_id", None)
        logger.error("unhandled_exception", error=str(exc), trace_id=trace_id)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": str(exc) if settings.debug else None,
                "trace_id": trace_id,
                "timestamp": utc_now_iso(),
            },
        )

    logger.info(
        "app_started",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    return app


app = create_app()


def custom_openapi():
    """
    Attach an HTTP Bearer security scheme so Swagger UI shows an Authorize button.
    Auth is still enforced by middleware; this is documentation + header wiring.
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        routes=app.routes,
    )

    components = openapi_schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }

    # Apply BearerAuth as the default security requirement for all endpoints
    openapi_schema["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
