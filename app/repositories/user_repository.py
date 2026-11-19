"""用户仓储。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """用户表数据访问。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_username(self, username: str) -> User | None:
        """按用户名查询。"""
        return self._session.scalar(select(User).where(User.username == username))

    def get_by_id(self, user_id: str) -> User | None:
        """按 id 查询。"""
        return self._session.get(User, user_id)

    def create(self, username: str, password_hash: str) -> User:
        """创建用户（调用方负责提交事务）。"""
        user = User(id=uuid.uuid4().hex, username=username, password_hash=password_hash)
        self._session.add(user)
        self._session.flush()
        return user
