"""应用配置。

所有可调参数集中在此，通过环境变量或项目根目录的 ``.env`` 覆盖。
业务代码只依赖 :class:`Settings`，不直接读 ``os.environ``。
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: 项目根目录（app/core/config.py -> app/core -> app -> 项目根）
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """运行时配置。字段名即环境变量名（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ 应用
    app_name: str = "AI Task Manager"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api"

    # ------------------------------------------------------------------ 数据
    data_dir: Path = Path("data")
    database_url: str | None = None

    # ------------------------------------------------------------------ 认证
    #: JWT 签名密钥。留空时自动生成随机密钥（重启后已登录状态失效）；
    #: 生产环境必须通过 SECRET_KEY 显式设置（至少 32 字符）。
    secret_key: str = Field(default_factory=lambda: secrets.token_hex(32))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=1440, ge=1, le=60 * 24 * 30)

    # ------------------------------------------------------------------ AI（可选）
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    # ------------------------------------------------------------------ 校验
    @model_validator(mode="after")
    def _validate_security(self) -> Settings:
        """生产环境强制显式设置高强度密钥；开发环境允许留空自动生成。"""
        if self.environment == "production" and len(self.secret_key) < 32:
            raise ValueError("生产环境必须设置至少 32 字符的 SECRET_KEY")
        if 0 < len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY 长度不足：至少 32 字符（JWT HS256 安全要求）")
        return self

    # ------------------------------------------------------------------ 派生配置
    @property
    def resolved_database_url(self) -> str:
        """默认 SQLite（DATA_DIR/app.db）；环境变量可指向 PostgreSQL。"""
        if self.database_url:
            return self.database_url
        db_file = (self.data_dir / "app.db").as_posix()
        return f"sqlite:///{db_file}"

    @property
    def ai_configured(self) -> bool:
        """AI 功能是否具备调用条件（三项齐全）。"""
        return bool(self.ai_base_url and self.ai_api_key and self.ai_model)

    def ensure_directories(self) -> None:
        """创建运行期必需的目录（幂等）。"""
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """进程级缓存的单例配置（供 CLI / 部署入口使用；测试自行构造 Settings）。"""
    return Settings()
