from pydantic import BaseModel, ConfigDict, Field
import uuid
from src.db.models.user import UserRole
from datetime import datetime

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    locked_until: datetime | None = None
    password_changed_at: datetime | None = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.\-]+$")
    role: UserRole
    password: str

class UserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

class PasswordResetRequest(BaseModel):
    new_password: str
