"""Bill calculator agent that delegates tariff math to MCP."""

from app.graph.state import HomeWattState
from app.mcp_client.client import (
    MCPClientError,
    calculate_budget_unit_limit_via_mcp,
)


async def bill_calculator_node(state: HomeWattState) -> HomeWattState:
    """Calculate the budget unit limit using the MCP server."""
    try:
        result = await calculate_budget_unit_limit_via_mcp(
            state["year"],
            state["month"],
            state["max_budget_lkr"],
        )
    except MCPClientError as exc:
        return {
            **state,
            "error": f"Could not calculate budget unit limit: {exc}",
        }

    required_fields = {
        "billing_days",
        "estimated_allowed_units",
        "estimated_bill",
    }
    if not isinstance(result, dict) or not required_fields.issubset(result):
        return {
            **state,
            "error": "Could not calculate budget unit limit: invalid MCP response.",
        }

    return {
        **state,
        "billing_days": result["billing_days"],
        "estimated_allowed_units": result["estimated_allowed_units"],
        "estimated_bill_at_limit": result["estimated_bill"],
        "budget_limit_result": result,
    }
