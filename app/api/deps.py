"""依赖注入：应用容器、数据库会话与当前登录用户。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.ai.service import AIService
from app.core.config import Settings
from app.core.errors import TokenError
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.stats_service import StatsService
from app.services.task_service import TaskService

#: auto_error=False：缺失时返回 None，由 get_current_user 统一抛 401 信封
bearer_scheme = HTTPBearer(auto_error=False)


class Container:
    """应用级容器：持有配置、数据库与各业务服务。"""

    def __init__(self, settings: Settings) -> None:
        from app.database.session import Database  # 局部导入避免循环

        self.settings = settings
        self.database = Database(settings)
        self.auth_service = AuthService(settings, self.database)
        self.task_service = TaskService(settings, self.database)
        self.stats_service = StatsService(settings, self.database)
        self.ai_service = AIService(settings, self.database)

    def dispose(self) -> None:
        """应用关闭时释放资源。"""
        self.database.dispose()


def get_container(request: Request) -> Container:
    """从 app.state 取应用容器。"""
    return request.app.state.container


def get_auth_service(container: Annotated[Container, Depends(get_container)]) -> AuthService:
    """认证服务。"""
    return container.auth_service


def get_task_service(container: Annotated[Container, Depends(get_container)]) -> TaskService:
    """任务服务。"""
    return container.task_service


def get_stats_service(container: Annotated[Container, Depends(get_container)]) -> StatsService:
    """统计服务。"""
    return container.stats_service


def get_ai_service(container: Annotated[Container, Depends(get_container)]) -> AIService:
    """AI 服务。"""
    return container.ai_service


def get_current_user(
    container: Annotated[Container, Depends(get_container)],
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """解析 Bearer 令牌并返回当前用户；失败统一 401。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise TokenError("缺少认证信息，请先登录")
    return container.auth_service.authenticate_token(credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]
