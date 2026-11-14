"""角色 -> 权限点映射。README 与前端 site/js/config.js 同步。

角色键固定为 admin / analyst / viewer，各项目的展示名与职责不同。
"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "会员运营管理员",
    Role.ANALYST.value: "会员数据专员",
    Role.VIEWER.value: "门店业务只读",
}

ROLE_DUTIES: dict[str, str] = {
    Role.ADMIN.value: "调 RFM 分位与权重、定券面额、生成名单、导出、看审计",
    Role.ANALYST.value: "看分群与 lift、复核名单口径、导出报表",
    Role.VIEWER.value: "只读查看分群与名单，手机号脱敏，不能重算或导出",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "member:read", "order:read",
        "segment:read", "segment:recompute", "segment:write",
        "campaign:read", "campaign:write",
        "audience:read", "audience:generate", "audience:confirm",
        "export:read", "audit:read", "overview:read",
    },
    Role.ANALYST.value: {
        "member:read", "order:read",
        "segment:read",
        "campaign:read",
        "audience:read", "audience:confirm",
        "export:read", "overview:read",
    },
    Role.VIEWER.value: {
        "member:read", "order:read", "segment:read", "campaign:read", "audience:read", "overview:read",
    },
}

SEGMENT_ADMIN_ROLES = (Role.ADMIN.value,)
CAMPAIGN_WRITE_ROLES = (Role.ADMIN.value,)
AUDIENCE_GENERATE_ROLES = (Role.ADMIN.value,)
AUDIENCE_CONFIRM_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
EXPORT_ROLES = (Role.ADMIN.value, Role.ANALYST.value)
AUDIT_ROLES = (Role.ADMIN.value,)
READ_ROLES = (Role.ADMIN.value, Role.ANALYST.value, Role.VIEWER.value)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
