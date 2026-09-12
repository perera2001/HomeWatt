"""LangChain tool wrappers for HomeWatt agents."""

import json
import math
from typing import Any

from langchain_core.tools import tool

from app.mcp_client.client import (
    classify_appliance_priority_via_mcp,
    get_mcp_prompt,
)


@tool
def validate_appliance_input_tool(
    year: int,
    month: int,
    max_budget_lkr: float,
    appliances_json: str,
) -> dict[str, Any]:
    """Validate extracted planning details without performing calculations."""
    try:
        appliances = json.loads(appliances_json)
    except json.JSONDecodeError:
        appliances = []

    errors = []
    if not year:
        errors.append("year is required")
    if not month or month < 1 or month > 12:
        errors.append("month must be between 1 and 12")
    if (
        isinstance(max_budget_lkr, bool)
        or not isinstance(max_budget_lkr, (int, float))
        or not math.isfinite(float(max_budget_lkr))
        or max_budget_lkr <= 0
    ):
        errors.append("budget must be greater than 0")
    if not appliances:
        errors.append("at least one appliance with watts and required hours per day is required")

    for appliance in appliances or []:
        name = str(appliance.get("name", "")).strip()
        watts = appliance.get("watts")
        required_hours = appliance.get("required_hours_per_day")
        if not name:
            errors.append("appliance name is required")
        if (
            isinstance(watts, bool)
            or not isinstance(watts, (int, float))
            or not math.isfinite(float(watts))
            or watts <= 0
        ):
            errors.append(f"watts must be greater than 0 for {name or 'an appliance'}")
        if required_hours is None:
            errors.append(
                f"required hours per day must be provided for {name or 'an appliance'}"
            )
        elif (
            isinstance(required_hours, bool)
            or not isinstance(required_hours, (int, float))
            or not math.isfinite(float(required_hours))
            or required_hours <= 0
        ):
            errors.append(
                f"required hours per day must be greater than 0 for {name or 'an appliance'}"
            )
        elif required_hours > 24:
            errors.append(
                f"required hours per day must not exceed 24 for {name or 'an appliance'}"
            )

    return {
        "is_valid": not errors,
        "errors": errors,
    }


@tool
async def classify_appliance_priority_tool(item_name: str) -> dict[str, Any]:
    """Classify an appliance priority through the MCP server."""
    return await classify_appliance_priority_via_mcp(item_name)


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
