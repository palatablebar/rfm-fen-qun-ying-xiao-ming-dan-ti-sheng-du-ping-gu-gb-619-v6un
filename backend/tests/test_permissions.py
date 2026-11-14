"""权限矩阵与手机号脱敏单测（横切：JWT 三角色）。"""
from __future__ import annotations

from src.constants.enums import Role
from src.constants.roles import (
    AUDIT_ROLES,
    EXPORT_ROLES,
    PERMISSIONS,
    SEGMENT_ADMIN_ROLES,
    has_permission,
)
from src.services.member_service import mask_phone


def test_viewer_cannot_export_or_read_audit():
    viewer = Role.VIEWER.value
    assert has_permission(viewer, "member:read") is True
    assert has_permission(viewer, "export:read") is False
    assert has_permission(viewer, "audit:read") is False
    assert has_permission(viewer, "segment:recompute") is False


def test_analyst_reads_but_does_not_recompute_or_export_audit():
    analyst = Role.ANALYST.value
    assert has_permission(analyst, "segment:read") is True
    assert has_permission(analyst, "audience:confirm") is True
    assert has_permission(analyst, "audience:generate") is False
    assert has_permission(analyst, "segment:recompute") is False
    assert analyst not in AUDIT_ROLES
    assert analyst in EXPORT_ROLES


def test_admin_owns_thresholds_and_export():
    admin = Role.ADMIN.value
    assert SEGMENT_ADMIN_ROLES == (admin,)
    assert has_permission(admin, "segment:recompute") is True
    assert has_permission(admin, "audit:read") is True
    assert set(PERMISSIONS[admin]) > set(PERMISSIONS[Role.ANALYST.value])


def test_phone_masking():
    assert mask_phone("13812345678") == "138****5678"
    assert mask_phone("") == "***"
    assert mask_phone("12345") == "***"
