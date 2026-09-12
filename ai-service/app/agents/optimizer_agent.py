"""Usage optimizer agent that delegates planning calculations to MCP."""

from app.graph.state import HomeWattState
from app.mcp_client.client import MCPClientError, generate_initial_usage_plan_via_mcp


async def usage_optimizer_node(state: HomeWattState) -> HomeWattState:
    """Generate the initial usage plan using the MCP server."""
    try:
        result = await generate_initial_usage_plan_via_mcp(
            state["year"],
            state["month"],
            state["max_budget_lkr"],
            state["appliances"],
        )
    except MCPClientError as exc:
        return {
            **state,
            "error": f"Could not generate usage plan: {exc}",
        }

    required_fields = {
        "requested_plan",
        "affordable_plan",
        "requested_total_units",
        "minimum_required_budget",
        "minimum_possible_bill",
        "budget_shortfall",
        "remaining_budget",
        "requirements_met",
        "adjustments_required",
        "budget_feasible",
        "total_units",
        "estimated_bill",
        "stays_within_budget",
    }
    if not isinstance(result, dict) or not required_fields.issubset(result):
        return {
            **state,
            "error": "Could not generate usage plan: invalid MCP response.",
        }

    return {
        **state,
        "usage_plan": result,
        "requested_plan": result["requested_plan"],
        "affordable_plan": result["affordable_plan"],
        "requested_total_units": result["requested_total_units"],
        "minimum_required_budget": result["minimum_required_budget"],
        "minimum_possible_bill": result["minimum_possible_bill"],
        "budget_shortfall": result["budget_shortfall"],
        "remaining_budget": result["remaining_budget"],
        "requirements_met": result["requirements_met"],
        "adjustments_required": result["adjustments_required"],
        "budget_feasible": result["budget_feasible"],
        "total_units": result["total_units"],
        "estimated_bill": result["estimated_bill"],
        "stays_within_budget": result["stays_within_budget"],
    }
