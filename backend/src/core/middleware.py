from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
import uuid
from src.core.logging import correlation_id_var

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        
        token = correlation_id_var.set(correlation_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            correlation_id_var.reset(token)


class BodySizeLimitMiddleware:
    """
    Refuses request bodies over `max_bytes` (413) before they are read: by their declared
    Content-Length up front, and while streaming when no length is declared. Without it a
    multipart upload is parsed in full, before authentication and the endpoint's own size check.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            response = JSONResponse({"detail": "Request body too large"}, status_code=413)
            return await response(scope, receive, send)

        received = 0
        too_large = False

        async def limited_receive():
            # Past the limit, end the body as if the client had gone away; the app's response
            # (an error about the unreadable body) is replaced with a 413 below.
            nonlocal received, too_large
            if too_large:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    too_large = True
                    return {"type": "http.disconnect"}
            return message

        replaced = False

        async def checked_send(message):
            nonlocal replaced
            if too_large and message["type"] == "http.response.start":
                replaced = True
                return await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
            if replaced:
                return  # the rest of the replaced response
            await send(message)

        await self.app(scope, limited_receive, checked_send)
