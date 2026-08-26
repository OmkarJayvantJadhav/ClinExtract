from fastapi import Request
from fastapi.responses import JSONResponse
import uuid

class APIException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

async def api_exception_handler(request: Request, exc: APIException):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=exc.code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "correlation_id": correlation_id
            }
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "correlation_id": correlation_id
            }
        }
    )
