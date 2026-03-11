from __future__ import annotations
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.constants import HeaderConstants
from app.core.utils import generate_request_id, generate_trace_id
from app.infrastructure.logging.logger import get_logger, request_id_ctx, trace_id_ctx

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        req_id = request.headers.get(HeaderConstants.REQUEST_ID) or generate_request_id()
        t_id = request.headers.get(HeaderConstants.TRACE_ID) or generate_trace_id()

        request_id_ctx.set(req_id)
        trace_id_ctx.set(t_id)

        request.state.request_id = req_id
        request.state.trace_id = t_id

        logger.info(
            "http_request_started",
            method=request.method,
            path=str(request.url.path),
            request_id=req_id,
            trace_id=t_id,
        )

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "http_request_completed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            request_id=req_id,
            trace_id=t_id,
        )

        response.headers[HeaderConstants.REQUEST_ID] = req_id
        response.headers[HeaderConstants.TRACE_ID] = t_id
        return response
