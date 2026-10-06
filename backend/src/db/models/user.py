from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Enum, Integer, DateTime
import enum
from datetime import datetime
from src.db.base import BaseModel

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    REVIEWER = "REVIEWER"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"

class User(BaseModel):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role_enum"))
    is_active: Mapped[bool] = mapped_column(default=True)

    # Brute-force protection
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # Incremented to revoke every session issued before (password change, deactivation, "log out everywhere")
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    documents = relationship("Document", back_populates="uploader")
    reviews = relationship("Review", back_populates="reviewer")
