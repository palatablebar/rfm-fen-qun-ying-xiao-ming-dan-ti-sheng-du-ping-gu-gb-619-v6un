"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.audiences import router as audiences_router
from src.routes.audit import router as audit_router
from src.routes.auth import router as auth_router
from src.routes.campaigns import router as campaigns_router
from src.routes.exports import router as exports_router
from src.routes.health import router as health_router
from src.routes.members import router as members_router
from src.routes.overview import router as overview_router
from src.routes.segments import router as segments_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(overview_router)
api_router.include_router(members_router)
api_router.include_router(segments_router)
api_router.include_router(campaigns_router)
api_router.include_router(audiences_router)
api_router.include_router(exports_router)
api_router.include_router(audit_router)
