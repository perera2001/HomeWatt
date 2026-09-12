"""FastMCP server for deterministic HomeWatt Advisor domain data and tools."""

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.appliance_rules import (
    PRIORITY_RULES,
    classify_appliance_priority_data,
    generate_initial_usage_plan_data,
)
from mcp_server.prompts import create_usage_guide_prompt, explain_bill_breakdown_prompt
from mcp_server.tariff_data import (
    TARIFF_DATA,
    calculate_appliance_kwh_data,
    calculate_budget_unit_limit_data,
    calculate_domestic_bill_data,
    get_billing_days_data,
)


mcp = FastMCP(
    "HomeWatt Advisor",
    instructions=(
        "Provides Sri Lankan domestic tariff data and deterministic electricity "
        "usage planning calculations. Use tools for all numeric calculations."
    ),
)


@mcp.resource(
    "tariff://sri-lanka/domestic/2026-05",
    mime_type="application/json",
    description="Sri Lankan domestic electricity tariff effective from 11 May 2026.",
)
def sri_lanka_domestic_tariff() -> str:
    """Return the approved May 2026 domestic tariff definition."""
    return json.dumps(TARIFF_DATA, indent=2)


@mcp.resource(
    "appliances://priority-rules",
    mime_type="application/json",
    description="Rule-based household appliance priorities for usage planning.",
)
def appliance_priority_rules() -> str:
    """Return deterministic appliance priority and category rules."""
    return json.dumps(PRIORITY_RULES, indent=2)


@mcp.tool()
def get_billing_days(year: int, month: int) -> dict[str, int]:
    """Return the number of billing days in a calendar month."""
    return get_billing_days_data(year, month)


@mcp.tool()
def calculate_appliance_kwh(
    watts: float, hours_per_day: float, days: int
) -> dict[str, float | int]:
    """Calculate appliance kWh as watts * hours/day * days / 1000."""
    return calculate_appliance_kwh_data(watts, hours_per_day, days)


@mcp.tool()
def calculate_domestic_bill(
    year: int,
    month: int,
    units: float,
    credit_balance: float = 0,
    debit_balance: float = 0,
) -> dict[str, Any]:
    """Calculate a Sri Lankan domestic bill using the May 2026 tariff."""
    return calculate_domestic_bill_data(year, month, units, credit_balance, debit_balance)


@mcp.tool()
def calculate_budget_unit_limit(
    year: int, month: int, max_budget_lkr: float
) -> dict[str, float | int]:
    """Estimate the maximum electricity units that fit a monthly budget."""
    return calculate_budget_unit_limit_data(year, month, max_budget_lkr)


@mcp.tool()
def classify_appliance_priority(item_name: str) -> dict[str, str]:
    """Classify an appliance as high, medium, or low priority."""
    return classify_appliance_priority_data(item_name)


@mcp.tool()
def generate_initial_usage_plan(
    year: int,
    month: int,
    max_budget_lkr: float,
    appliances: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare required daily hours with the budget and suggest adjustments."""
    return generate_initial_usage_plan_data(year, month, max_budget_lkr, appliances)


@mcp.prompt(name="create_usage_guide")
def create_usage_guide(
    year: int,
    month: int,
    max_budget_lkr: float,
    appliances: str,
    usage_plan: str,
    bill_breakdown: str,
) -> str:
    """Create a grounded household electricity usage-guide prompt."""
    return create_usage_guide_prompt(
        year, month, max_budget_lkr, appliances, usage_plan, bill_breakdown
    )


@mcp.prompt(name="explain_bill_breakdown")
def explain_bill_breakdown(bill_breakdown: str) -> str:
    """Create a grounded plain-language bill explanation prompt."""
    return explain_bill_breakdown_prompt(bill_breakdown)


if __name__ == "__main__":
    mcp.run(transport="stdio")
