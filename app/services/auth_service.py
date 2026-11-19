"""认证服务：注册、登录、令牌校验。"""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import InvalidCredentialsError, TokenError, UsernameTakenError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.database.session import Database
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    """认证业务：密码哈希、用户创建、令牌签发与解析。"""

    def __init__(self, settings: Settings, database: Database) -> None:
        self._settings = settings
        self._database = database

    def register(self, username: str, password: str) -> User:
        """注册新用户；用户名重复抛 UsernameTakenError。"""
        password_hash = hash_password(password)
        with self._database.session() as session:
            repository = UserRepository(session)
            if repository.get_by_username(username) is not None:
                raise UsernameTakenError(f"用户名已被占用：{username}")
            return repository.create(username=username, password_hash=password_hash)

    def login(self, username: str, password: str) -> tuple[User, str]:
        """登录成功返回 (用户, 访问令牌)；失败统一抛 401（不区分具体原因）。"""
        with self._database.session() as session:
            user = UserRepository(session).get_by_username(username)
            if user is None or not verify_password(password, user.password_hash):
                raise InvalidCredentialsError("用户名或密码错误")
            return user, self.issue_token(user)

    def authenticate_token(self, token: str) -> User:
        """校验令牌并返回对应用户；令牌无效或用户不存在统一抛 401。"""
        user_id = decode_access_token(
            token,
            secret_key=self._settings.secret_key,
            algorithm=self._settings.jwt_algorithm,
        )
        with self._database.session() as session:
            user = UserRepository(session).get_by_id(user_id)
        if user is None:
            raise TokenError("令牌无效")
        return user

    def issue_token(self, user: User) -> str:
        """为用户签发访问令牌。"""
        return create_access_token(
            user_id=user.id,
            secret_key=self._settings.secret_key,
            algorithm=self._settings.jwt_algorithm,
            expires_minutes=self._settings.jwt_expire_minutes,
        )
