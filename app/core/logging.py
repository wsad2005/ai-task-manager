"""日志：统一格式与获取函数；入口处配置一次。"""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """配置根日志；重复调用只调整级别，不叠加 handler。"""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger().setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    """按模块名获取 logger。"""
    return logging.getLogger(name)
