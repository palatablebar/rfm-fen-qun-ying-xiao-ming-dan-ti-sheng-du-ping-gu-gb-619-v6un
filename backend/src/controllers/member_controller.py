"""会员与订单控制器：viewer 返回脱敏手机号。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.constants.enums import Role
from src.services import audit_service, member_service


def _mask(principal: dict) -> bool:
    return principal.get("role") == Role.VIEWER.value


def list_members(db: Session, principal: dict, **filters) -> dict:
    return member_service.list_members(db, mask=_mask(principal), **filters)


def get_member(db: Session, member_id: int, principal: dict, request: Request) -> dict:
    payload = member_service.get_member(db, member_id, mask=_mask(principal))
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="member.view",
        entity="member",
        entity_id=member_id,
        detail={"member_no": payload["member_no"], "masked": _mask(principal)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return payload


def list_orders(db: Session, **filters) -> dict:
    return member_service.list_orders(db, **filters)
