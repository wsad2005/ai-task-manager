"""声明式基类与公共混入。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now_local() -> datetime:
    """本地时区 aware 时间：任务管理以用户本地日历为准（趋势/逾期按本地日期）。"""
    return datetime.now().astimezone()


class Base(DeclarativeBase):
    """全部 ORM 模型的声明式基类。"""


class TimestampMixin:
    """created_at / updated_at 时间戳（本地时区，带 tzinfo）。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=now_local,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=now_local,
        onupdate=now_local,
    )
