"""导出控制器：CSV 响应 + 审计。"""
from __future__ import annotations

from fastapi import Request, Response
from sqlalchemy.orm import Session

from src.services import audit_service, export_service
from src.utils.csv_export import csv_response_headers


def _response(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=csv_response_headers(filename))


def members_csv(db: Session, principal: dict, request: Request) -> Response:
    content = export_service.members_csv(db)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.members",
        entity="member",
        entity_id=None,
        detail={"bytes": len(content)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return _response(content, "members.csv")


def segments_csv(db: Session, principal: dict, request: Request) -> Response:
    content = export_service.segments_csv(db)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.segments",
        entity="segment",
        entity_id=None,
        detail={"bytes": len(content)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return _response(content, "segments.csv")


def audiences_csv(db: Session, audience_id: int | None, principal: dict, request: Request) -> Response:
    content = export_service.audience_csv(db, audience_id)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.audiences",
        entity="audience",
        entity_id=audience_id,
        detail={"bytes": len(content)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return _response(content, "audience.csv")
