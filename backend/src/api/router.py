from fastapi import APIRouter
from src.core.config import settings
from src.api.routes import health, auth, users, documents, jobs, reviews, analytics, audit

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
api_router.include_router(reviews.router, tags=["Reviews"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])

if settings.APP_ENV == "testing":
    from src.api.routes import rbac_probe
    api_router.include_router(rbac_probe.router, prefix="/users", tags=["Testing"])
