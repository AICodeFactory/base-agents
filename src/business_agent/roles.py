from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RoleContext:
    """Business identity attached to one agent request."""

    role: str
    user_id: str | None = None
    tenant_id: str | None = None
    permissions: Iterable[str] = field(default_factory=tuple)
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "permissions", frozenset(self.permissions))
        object.__setattr__(self, "attributes", dict(self.attributes))

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_permissions(self, permissions: Iterable[str]) -> bool:
        return set(permissions).issubset(self.permissions)

    def matches_role(self, allowed_roles: Iterable[str] | None) -> bool:
        allowed = set(allowed_roles or ())
        return not allowed or "*" in allowed or self.role in allowed

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "permissions": sorted(self.permissions),
            "attributes": dict(self.attributes),
        }
