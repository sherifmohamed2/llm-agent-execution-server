from __future__ import annotations
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.constants import HeaderConstants
from app.core.utils import utc_now_iso
from app.infrastructure.logging.logger import get_logger
from app.infrastructure.security.jwt import decode_token

logger = get_logger(__name__)

SKIP_AUTH_PATHS = {
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        if path in SKIP_AUTH_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        auth_header = request.headers.get(HeaderConstants.AUTHORIZATION, "")

        if not auth_header.startswith(HeaderConstants.BEARER_PREFIX):
            logger.warning("auth_missing_or_invalid_header", path=path)
            return JSONResponse(
                status_code=401,
                content={
                    "error_code": "UNAUTHORIZED",
                    "message": "Missing or invalid Authorization header",
                    "details": None,
                    "trace_id": getattr(request.state, "trace_id", None),
                    "timestamp": utc_now_iso(),
                },
            )

        token = auth_header[len(HeaderConstants.BEARER_PREFIX) :]
        try:
            payload = decode_token(token)
            request.state.user_id = payload.get("sub", "")
            request.state.user_role = payload.get("role", "user")
        except Exception as exc:
            # Log the detailed reason internally 
            logger.warning("auth_token_invalid", path=path, error=str(exc))
            return JSONResponse(
                status_code=401,
                content={
                    "error_code": "UNAUTHORIZED",
                    "message": "Authentication failed",
                    "details": None,
                    "trace_id": getattr(request.state, "trace_id", None),
                    "timestamp": utc_now_iso(),
                },
            )

        return await call_next(request)
