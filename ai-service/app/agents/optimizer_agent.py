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

    return {
        **state,
        "usage_plan": result,
        "total_units": result["total_units"],
        "estimated_bill": result["estimated_bill"],
        "stays_within_budget": result["stays_within_budget"],
    }
