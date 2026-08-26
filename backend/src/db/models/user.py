from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Enum
import enum
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

    documents = relationship("Document", back_populates="uploader")
    reviews = relationship("Review", back_populates="reviewer")
