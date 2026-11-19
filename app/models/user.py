"""用户模型。"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """用户：仅存用户名与密码哈希，绝不存明文密码。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<User id={self.id} username={self.username!r}>"
