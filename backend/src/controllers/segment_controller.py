"""分群控制器：重算与券口径调整都落审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, segment_service


def list_segments(db: Session) -> dict:
    return segment_service.list_segments(db)


def recompute(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    weights = (
        float(payload.get("weight_r", 0.3)),
        float(payload.get("weight_f", 0.3)),
        float(payload.get("weight_m", 0.4)),
    )
    result = segment_service.recompute(db, weights=weights, window_days=int(payload.get("window_days", 365)))
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="segment.recompute",
        entity="segment",
        entity_id=None,
        detail={
            "weights": list(weights),
            "window_days": result["window_days"],
            "as_of": result["as_of"],
            "members": result["member_count"],
            "thresholds": result["thresholds"],
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return result


def update_segment(db: Session, segment_id: int, payload: dict, principal: dict, request: Request) -> dict:
    segment = segment_service.get_segment(db, segment_id)
    segment_service.update_segment(db, segment, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="segment.update",
        entity="segment",
        entity_id=segment.id,
        detail={"fields": list(payload.keys()), "code": segment.code},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return segment_service.serialize(segment)
