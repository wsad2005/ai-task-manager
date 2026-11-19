"""Alembic 迁移环境。

数据库地址的优先级：
1. ``alembic -x db_url=...`` 显式传入；
2. 编程调用时注入的 ``sqlalchemy.url``（app/database/migrations.py，测试用）；
3. 回退到 ``app.core.config.Settings``（环境变量 / .env）。
模型变更后用 ``alembic revision --autogenerate -m "..."`` 生成新版本。
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import Settings
from app.models import Base  # noqa: F401  导入以注册全部模型元数据

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    """按优先级解析迁移目标数据库。"""
    x_args = context.get_x_argument(as_dictionary=True)
    if x_args.get("db_url"):
        return x_args["db_url"]
    programmatic_url = config.get_main_option("sqlalchemy.url")
    if programmatic_url:
        return programmatic_url
    return Settings().resolved_database_url


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL 脚本，不连接数据库。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
