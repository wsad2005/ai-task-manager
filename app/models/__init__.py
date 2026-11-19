"""ORM 模型包：导入即注册全部模型到 Base.metadata。"""

from app.models.base import Base
from app.models.task import Task
from app.models.user import User

__all__ = ["Base", "Task", "User"]
