"""数据库迁移测试：Alembic 升级、幂等性与外键。"""

from sqlalchemy import create_engine, inspect

from app.core.config import Settings
from app.database.migrations import run_migrations


def _fresh_settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        data_dir=tmp_path / "data",
        log_level="WARNING",
    )


def test_upgrade_creates_all_tables(tmp_path) -> None:
    settings = _fresh_settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"users", "tasks", "alembic_version"} <= tables


def test_upgrade_is_idempotent(tmp_path) -> None:
    settings = _fresh_settings(tmp_path)
    run_migrations(settings)
    run_migrations(settings)  # 第二次应为 no-op，不报错
    engine = create_engine(settings.resolved_database_url)
    assert {"users", "tasks"} <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_migrated_schema_supports_fk(tmp_path) -> None:
    """迁移后的库可直接承接业务写入（外键约束由连接级 PRAGMA 开启）。"""
    settings = _fresh_settings(tmp_path)
    run_migrations(settings)
    from app.database.session import Database

    database = Database(settings)
    with database.session() as session:
        session.execute(
            __import__("sqlalchemy")
            .text("INSERT INTO users (id, username, password_hash) VALUES ('u1', 'alice', 'x')")
        )
        session.execute(
            __import__("sqlalchemy").text(
                "INSERT INTO tasks (id, user_id, title) VALUES ('t1', 'u1', '任务')"
            )
        )
    database.dispose()
