import asyncio

import pytest

from business_agent import RoleContext, ToolAccessError, ToolRegistry, business_tool


def test_registry_filters_tools_by_role_and_permission() -> None:
    @business_tool(
        name="query_orders",
        allowed_roles=["sales_manager"],
        required_permissions=["order:read"],
    )
    def query_orders() -> list[str]:
        return []

    @business_tool(name="public_help")
    def public_help() -> str:
        return "help"

    registry = ToolRegistry([query_orders, public_help])

    sales_role = RoleContext(role="sales_manager", permissions=["order:read"])
    guest_role = RoleContext(role="guest")

    assert [tool.name for tool in registry.visible_tools_for(sales_role)] == [
        "query_orders",
        "public_help",
    ]
    assert [tool.name for tool in registry.visible_tools_for(guest_role)] == ["public_help"]


def test_tool_injects_role_context() -> None:
    @business_tool(name="whoami", allowed_roles=["admin"])
    def whoami(role_context: RoleContext) -> str:
        return role_context.role

    result = asyncio.run(whoami.ainvoke(RoleContext(role="admin")))

    assert result == "admin"


def test_tool_rejects_invisible_role() -> None:
    @business_tool(name="admin_only", allowed_roles=["admin"])
    def admin_only() -> str:
        return "secret"

    with pytest.raises(ToolAccessError):
        asyncio.run(admin_only.ainvoke(RoleContext(role="guest")))
