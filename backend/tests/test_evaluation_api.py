"""端到端接口测试：鉴权 / 导入幂等 / 发布锁定 / 导出与页面共用四个数字。

用 SQLite 覆盖 DBSession（生产用 PostgreSQL，ORM 与 JSON 字段行为一致）。
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import database
from src.config.database import get_db
from src.models import Base
from src.models.audience import Audience
from src.models.campaign import Campaign
from src.models.evaluation import Evaluation
from src.models.member import Member


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)

    def _get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    from src.main import app

    app.dependency_overrides[get_db] = _get_db
    monkeypatch.setattr(database, "wait_for_db", lambda *a, **k: True)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr("src.config.app._bootstrap_database", lambda: None)
    monkeypatch.setattr("src.config.app._run_seed_once", lambda: None)
    with TestClient(app) as test_client:
        test_client.db_factory = TestingSession
        yield test_client
    app.dependency_overrides.clear()


def _seed(client, *, members=300, allocated=100):
    from scripts.demo_config import DEMO_PASSWORD

    db = client.db_factory()
    member_rows = []
    for index in range(members):
        member = Member(
            member_no=f"E{index:05d}",
            name=f"会员{index}",
            phone="13800000000",
            city="上海",
            tier="normal",
            joined_on=date(2025, 1, 1),
            purchase_rate=0.05,
            avg_ticket=30.0,
            composite_score=1000 - index,
            segment_code="champion",
        )
        db.add(member)
        member_rows.append(member)
    campaign = Campaign(code="e2e-campaign", name="E2E 活动", budget=1200, status="active", operator_email="x@y.z")
    db.add(campaign)
    db.flush()
    audience = Audience(
        audience_no="A-E2E-01",
        campaign_id=campaign.id,
        status="pending",
        budget=90,
        member_count=allocated,
        spend=90,
        allocation=[{"segment_code": "champion", "segment_name": "重要价值", "status": "allocated", "allocated": allocated, "budget": 90}],
        operator_email="x@y.z",
    )
    db.add(audience)
    db.commit()
    ids = {"campaign_id": campaign.id, "audience_id": audience.id, "members": [m.member_no for m in member_rows]}
    db.close()
    return ids, DEMO_PASSWORD


def _login(client, email, password="Demo@2026"):
    from src.utils.security import hash_password

    db = client.db_factory()
    from src.models.user import User

    if db.query(User).filter(User.email == email).first() is None:
        db.add(User(email=email, password_hash=hash_password(password), display_name=email, role=email.split("@")[0]))
        db.commit()
    db.close()
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_end_to_end_import_publish_and_export(client):
    ids, password = _seed(client)
    admin = _login(client, "admin@rfmseg.io", password)

    # 确认名单即冻结对照组
    response = client.patch(
        f"/api/audiences/{ids['audience_id']}/review", json={"status": "confirmed"}, headers=admin
    )
    assert response.status_code == 200, response.text
    evaluation = response.json()["evaluation"]
    assert evaluation["status"] == "in_progress"
    assert evaluation["treated_count"] == 90
    assert evaluation["control_count"] == 10

    db = client.db_factory()
    frozen = db.get(Evaluation, evaluation["id"])
    treated_members = [db.get(Member, member_id) for member_id in frozen.treated_members]
    control_members = [db.get(Member, member_id) for member_id in frozen.control_members]
    db.close()

    rows = [
        {"member_no": member.member_no, "redeemed": True, "orders": 1, "gmv": 40, "as_of": "2026-10-08"}
        for member in treated_members[:27]
    ] + [
        {"member_no": member.member_no, "redeemed": False, "orders": 1, "gmv": 40, "as_of": "2026-10-08"}
        for member in control_members[:2]
    ]
    body = {"campaign_id": ids["campaign_id"], "batch_no": "E2E-1", "as_of": "2026-10-08", "rows": rows}
    first = client.post("/api/evaluations/import", json=body, headers=admin)
    assert first.status_code == 201, first.text
    assert first.json()["applied"] == 29
    assert first.json()["duplicate"] is False

    # 同批次重试：不新增、不重复应用
    again = client.post("/api/evaluations/import", json=body, headers=admin)
    assert again.status_code == 201, again.text
    assert again.json()["duplicate"] is True
    assert again.json()["applied"] == 0

    # 发布 → 已发布
    published = client.post(f"/api/evaluations/{evaluation['id']}/publish", json={}, headers=admin)
    assert published.status_code == 200, published.text
    detail = published.json()
    assert detail["status"] == "published"
    assert detail["status_label"] == "已发布"
    assert detail["treated_count"] == 90
    assert detail["control_count"] == 10
    assert detail["incremental_rate"] == pytest.approx(0.10)
    # 处理组 90 人 × 人均差 ¥4 = 增量 GMV 360；实花按处理组占比折算 90×90/100 = 81 → ROI 4.44
    assert detail["inc_gmv"] == pytest.approx(360.0)
    assert detail["spend"] == pytest.approx(81.0)
    assert detail["roi"] == pytest.approx(4.44)

    # 晚到批次不再改动已发布评估
    late = client.post(
        "/api/evaluations/import",
        json={**body, "batch_no": "E2E-2", "as_of": "2026-10-10",
              "rows": [{"member_no": member.member_no, "redeemed": True, "orders": 1, "gmv": 40} for member in treated_members[:45]]},
        headers=admin,
    )
    assert late.status_code == 201, late.text
    after = client.get(f"/api/evaluations/{evaluation['id']}", headers=admin).json()
    assert after["incremental_rate"] == pytest.approx(detail["incremental_rate"])
    assert after["roi"] == pytest.approx(detail["roi"])

    # 导出与页面同源：CSV 里的四个数字与 detail 一致
    content = client.get(f"/api/exports/evaluations.csv?campaign_id={ids['campaign_id']}", headers=admin).text
    lines = [line for line in content.splitlines() if line.strip()]
    assert "处理人数" in lines[0]
    row = next(line for line in lines[1:] if "A-E2E-01" in line)
    cells = row.split(",")
    assert cells[3] == "90"  # 处理人数
    assert cells[4] == "10"  # 对照人数
    assert cells[5] == "10.00%"  # 增量率
    assert cells[6] == "4.44"  # ROI


def test_viewer_cannot_import_or_publish(client):
    ids, password = _seed(client)
    viewer = _login(client, "viewer@rfmseg.io", password)
    admin = _login(client, "admin@rfmseg.io", password)
    client.patch(f"/api/audiences/{ids['audience_id']}/review", json={"status": "confirmed"}, headers=admin)
    evaluation = client.get(f"/api/evaluations?campaign_id={ids['campaign_id']}", headers=viewer).json()["items"][0]

    assert client.post(
        "/api/evaluations/import",
        json={"campaign_id": ids["campaign_id"], "batch_no": "X", "rows": []},
        headers=viewer,
    ).status_code == 403
    assert client.post(f"/api/evaluations/{evaluation['id']}/publish", json={}, headers=viewer).status_code == 403


def test_duplicate_batch_number_with_different_content_conflicts(client):
    ids, password = _seed(client)
    admin = _login(client, "admin@rfmseg.io", password)
    client.patch(f"/api/audiences/{ids['audience_id']}/review", json={"status": "confirmed"}, headers=admin)
    body = {
        "campaign_id": ids["campaign_id"],
        "batch_no": "DUP-1",
        "as_of": "2026-10-08",
        "rows": [{"member_no": ids["members"][0], "redeemed": True, "orders": 1, "gmv": 30}],
    }
    assert client.post("/api/evaluations/import", json=body, headers=admin).status_code == 201
    body["rows"] = [{"member_no": ids["members"][1], "redeemed": True, "orders": 1, "gmv": 30}]
    assert client.post("/api/evaluations/import", json=body, headers=admin).status_code == 409
