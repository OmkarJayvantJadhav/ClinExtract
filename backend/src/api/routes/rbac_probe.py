"""
RBAC / CSRF probe endpoints used by the test suite.

They are only mounted when APP_ENV == "testing" (see src/api/router.py) and return no data,
so they never expose user records in a real deployment.
"""
from fastapi import APIRouter, Depends

from src.db.models.user import User, UserRole
from src.api.deps import require_roles, get_current_user

router = APIRouter()

@router.get("/admin-only")
async def probe_admin(current_user: User = Depends(require_roles([UserRole.ADMIN]))):
    return {"status": "ok"}

@router.get("/reviewer-plus")
async def probe_reviewer(current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER]))):
    return {"status": "ok"}

@router.get("/operator-plus")
async def probe_operator(current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER, UserRole.OPERATOR]))):
    return {"status": "ok"}

@router.get("/viewer-plus")
async def probe_viewer(current_user: User = Depends(get_current_user)):
    return {"status": "ok"}

@router.post("/dummy-mutation")
async def dummy_mutation(current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.REVIEWER, UserRole.OPERATOR]))):
    return {"status": "success"}
