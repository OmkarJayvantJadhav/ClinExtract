from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from starlette.formparsers import MultiPartParser
from src.core.middleware import BodySizeLimitMiddleware, CorrelationIdMiddleware
from src.core.metrics import MetricsMiddleware
from src.core.exceptions import APIException, api_exception_handler, global_exception_handler
from src.api.router import api_router
from src.core.logging import setup_logging
from src.storage.service import MAX_FILE_SIZE

# Largest request body: a document at the upload limit plus multipart overhead
MAX_REQUEST_BYTES = MAX_FILE_SIZE + 1024 * 1024
# Keep uploads in memory up to that size: by default parts over 1 MB are spooled to an
# unencrypted temporary file before the document is encrypted into storage.
MultiPartParser.spool_max_size = MAX_REQUEST_BYTES

def create_app() -> FastAPI:
    # Setup structured logging
    setup_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.APP_ENV != "production" else None,
        docs_url=f"{settings.API_V1_PREFIX}/docs" if settings.APP_ENV != "production" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(MetricsMiddleware)
    # Outermost: refuse oversized bodies before anything reads them
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)

    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app

app = create_app()
