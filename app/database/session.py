"""数据库引擎与会话管理（SQLAlchemy 2.x 同步用法）。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Database:
    """持有引擎与会话工厂；按需打开短事务会话。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine = create_engine(
            settings.resolved_database_url,
            echo=settings.debug,
            future=True,
        )
        if self._engine.url.get_backend_name() == "sqlite":
            # SQLite 默认不开外键约束，必须每个连接显式开启
            event.listen(self._engine, "connect", _enable_sqlite_fk)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """短事务会话：正常提交，异常回滚。"""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        """释放连接池（应用关闭时调用）。"""
        self._engine.dispose()
        logger.info("数据库连接池已释放")


def _enable_sqlite_fk(dbapi_connection: object, _record: object) -> None:
    """为每个 SQLite 连接开启外键约束。"""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
