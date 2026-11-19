"""迁移执行：用 Alembic 的编程接口把数据库升级到最新版本。

应用启动与测试夹具都走这里，保证“建表只通过迁移”这一条路径；
幂等调用（已是最新版本时为 no-op），绝不删除或重建数据。
"""

from __future__ import annotations

from alembic.config import Config

from alembic import command
from app.core.config import PROJECT_ROOT, Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def run_migrations(settings: Settings) -> None:
    """把 settings 指向的数据库升级到 head；重复调用安全。"""
    settings.ensure_directories()  # SQLite 需要父目录已存在
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    # URL 中的 '%' 必须转义成 '%%'，否则会被 configparser 当作插值符
    cfg.set_main_option("sqlalchemy.url", settings.resolved_database_url.replace("%", "%%"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    logger.info("数据库迁移已应用：%s", settings.resolved_database_url.split("://", 1)[0] + "://…")
