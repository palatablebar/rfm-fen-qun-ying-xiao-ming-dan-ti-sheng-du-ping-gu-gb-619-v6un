"""测试夹具：内存 SQLite + 最小会员/活动/名单数据集（不依赖 PostgreSQL）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.models import Base
from src.models.audience import Audience
from src.models.campaign import Campaign
from src.models.member import Member
from src.utils.timeutil import utcnow


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_members(db: Session, count: int, *, segment: str, seed: int = 0, rate: float = 0.05, ticket: float = 30.0):
    members = []
    for index in range(count):
        member = Member(
            member_no=f"T{seed + index:05d}",
            name=f"测试{seed + index}",
            phone="13800000000",
            city="上海",
            tier="normal",
            joined_on=utcnow().date(),
            purchase_rate=rate,
            avg_ticket=ticket,
            composite_score=1000 - index,
            segment_code=segment,
        )
        db.add(member)
        members.append(member)
    db.flush()
    return members


def add_campaign(db: Session, code: str = "test-campaign", budget: float = 1000.0) -> Campaign:
    campaign = Campaign(code=code, name="测试活动", budget=budget, status="active", operator_email="test@rfmseg.io")
    db.add(campaign)
    db.flush()
    return campaign


def add_audience(
    db: Session,
    campaign: Campaign,
    *,
    audience_no: str = "A2026111401",
    segment: str = "champion",
    allocated: int = 100,
    spend: float = 60.0,
) -> Audience:
    audience = Audience(
        audience_no=audience_no,
        campaign_id=campaign.id,
        status="pending",
        budget=spend,
        member_count=allocated,
        spend=spend,
        allocation=[
            {
                "segment_code": segment,
                "segment_name": segment,
                "status": "allocated",
                "allocated": allocated,
                "budget": spend,
                "inc_orders": 0,
                "roi": 0.0,
            }
        ],
        operator_email="test@rfmseg.io",
    )
    db.add(audience)
    db.flush()
    return audience
