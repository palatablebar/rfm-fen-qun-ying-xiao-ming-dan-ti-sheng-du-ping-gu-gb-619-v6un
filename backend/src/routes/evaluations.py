from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import EVALUATION_IMPORT_ROLES, EVALUATION_PUBLISH_ROLES
from src.controllers import evaluation_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.evaluation import EvaluationPublishIn, SettlementImportIn

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("")
def list_evaluations(
    campaign_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return evaluation_controller.list_for_campaign(db, campaign_id)


@router.get("/{evaluation_id}")
def get_evaluation(
    evaluation_id: int,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return evaluation_controller.detail(db, evaluation_id)


@router.post("/import", status_code=201)
def import_settlement(
    payload: SettlementImportIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EVALUATION_IMPORT_ROLES)),
) -> dict:
    return evaluation_controller.import_settlement(db, payload.model_dump(), principal, request)


@router.post("/{evaluation_id}/publish")
def publish_evaluation(
    evaluation_id: int,
    payload: EvaluationPublishIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*EVALUATION_PUBLISH_ROLES)),
) -> dict:
    return evaluation_controller.publish(db, evaluation_id, payload.model_dump(), principal, request)
