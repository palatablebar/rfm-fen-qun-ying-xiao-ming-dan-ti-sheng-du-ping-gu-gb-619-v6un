"""ORM 模型聚合导出（Base 用于 create_all）。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.models.user import User  # noqa: E402
from src.models.audit import AuditLog  # noqa: E402
from src.models.member import Member  # noqa: E402
from src.models.order import Order  # noqa: E402
from src.models.segment import Segment  # noqa: E402
from src.models.campaign import Campaign  # noqa: E402
from src.models.audience import Audience  # noqa: E402

__all__ = ["Base", "User", "AuditLog", "Member", "Order", "Segment", "Campaign", "Audience"]
