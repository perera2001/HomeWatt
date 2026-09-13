"""LangChain tool wrappers for HomeWatt agents."""

import json
from typing import Any

from langchain_core.tools import tool

from app.mcp_client.client import (
    get_mcp_prompt,
    read_appliance_priority_rules_via_mcp,
    read_tariff_resource_via_mcp,
)


@tool
async def read_tariff_resource_tool() -> dict[str, Any]:
    """Read the Sri Lankan domestic tariff MCP resource."""
    return await read_tariff_resource_via_mcp()


@tool
async def read_appliance_priority_rules_tool() -> dict[str, Any]:
    """Read the appliance-priority MCP resource."""
    return await read_appliance_priority_rules_via_mcp()


@tool
async def get_usage_guide_prompt_tool(
    year: int,
    month: int,
    max_budget_lkr: float,
    appliances_json: str,
    usage_plan_json: str,
    bill_breakdown_json: str,
) -> str:
    """Fetch the MCP usage-guide prompt for grounded guide writing."""
    return await get_mcp_prompt(
        "create_usage_guide",
        {
            "year": year,
            "month": month,
            "max_budget_lkr": max_budget_lkr,
            "appliances": appliances_json,
            "usage_plan": usage_plan_json,
            "bill_breakdown": bill_breakdown_json,
        },
    )


@tool
async def get_bill_breakdown_prompt_tool(bill_breakdown_json: str) -> str:
    """Fetch the MCP bill-breakdown explanation prompt."""
    return await get_mcp_prompt(
        "explain_bill_breakdown",
        {"bill_breakdown": bill_breakdown_json},
    )


def dumps_for_prompt(value: Any) -> str:
    """Serialize state data for prompt tools."""
    return json.dumps(value, indent=2)
