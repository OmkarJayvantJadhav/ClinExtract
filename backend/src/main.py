from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.core.middleware import CorrelationIdMiddleware
from src.core.metrics import MetricsMiddleware
from src.core.exceptions import APIException, api_exception_handler, global_exception_handler
from src.api.router import api_router
from src.core.logging import setup_logging

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

    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app

app = create_app()
