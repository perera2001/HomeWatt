"""Rule-based appliance priorities and initial usage planning."""

import math
import re
from typing import Any

from mcp_server.tariff_data import (
    calculate_appliance_kwh_data,
    calculate_budget_unit_limit_data,
    calculate_domestic_bill_data,
)


PRIORITY_RULES: dict[str, Any] = {
    "water motor": {
        "priority": "high",
        "category_note": "Required household water supply; protect reasonable usage.",
    },
    "refrigerator/fridge": {
        "priority": "high",
        "category_note": "Required continuous food storage; protect reasonable usage.",
    },
    "lights": {
        "priority": "high",
        "category_note": "Important household lighting; avoid unnecessary operation.",
    },
    "fan": {
        "priority": "high",
        "category_note": "High comfort priority in warm weather; use occupied rooms first.",
    },
    "rice cooker": {
        "priority": "medium",
        "category_note": "Moderate essential use; avoid extended keep-warm operation.",
    },
    "washing machine": {
        "priority": "medium",
        "category_note": "Moderate priority; combine clothes into full loads.",
    },
    "iron": {
        "priority": "medium",
        "category_note": "High-wattage appliance; use briefly and iron clothes in batches.",
    },
    "TV": {
        "priority": "low",
        "category_note": "Optional entertainment load; reduce this usage first.",
    },
    "decorative lights": {
        "priority": "low",
        "category_note": "Optional lighting load; reduce or disable this usage first.",
    },
    "unknown appliance": {
        "priority": "medium",
        "category_note": "No specific rule is available, so medium priority is used.",
    },
}


def normalize_appliance_name(item_name: str) -> str:
    """Normalize an appliance name for deterministic rule matching."""
    if not isinstance(item_name, str) or not item_name.strip():
        raise ValueError("item_name is required")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", item_name.lower())).strip()


def classify_appliance_priority_data(item_name: str) -> dict[str, str]:
    """Classify a known appliance, defaulting unknown items to medium."""
    normalized_name = normalize_appliance_name(item_name)
    name_tokens = normalized_name.split()

    if "decorative" in normalized_name and "light" in normalized_name:
        rule_key = "decorative lights"
    elif "water motor" in normalized_name or "water pump" in normalized_name:
        rule_key = "water motor"
    elif "refrigerator" in normalized_name or "fridge" in normalized_name:
        rule_key = "refrigerator/fridge"
    elif "washing machine" in normalized_name or "washer" in normalized_name:
        rule_key = "washing machine"
    elif "rice cooker" in normalized_name:
        rule_key = "rice cooker"
    elif "light" in normalized_name or "lamp" in normalized_name:
        rule_key = "lights"
    elif "fan" in normalized_name:
        rule_key = "fan"
    elif "iron" in normalized_name:
        rule_key = "iron"
    elif "tv" in name_tokens or "television" in name_tokens:
        rule_key = "TV"
    else:
        rule_key = "unknown appliance"

    rule = PRIORITY_RULES[rule_key]
    return {
        "item_name": item_name.strip(),
        "normalized_name": normalized_name,
        "priority": rule["priority"],
        "category_note": rule["category_note"],
    }


def _baseline_hours(normalized_name: str, priority: str) -> float:
    name_tokens = normalized_name.split()
    if "decorative" in normalized_name and "light" in normalized_name:
        return 1.0
    if "water motor" in normalized_name or "water pump" in normalized_name:
        return 0.5
    if "refrigerator" in normalized_name or "fridge" in normalized_name:
        return 8.0
    if "washing machine" in normalized_name or "washer" in normalized_name:
        return 0.4
    if "rice cooker" in normalized_name:
        return 1.0
    if "light" in normalized_name or "lamp" in normalized_name:
        return 5.0
    if "fan" in normalized_name:
        return 6.0
    if "iron" in normalized_name:
        return 0.25
    if "tv" in name_tokens or "television" in name_tokens:
        return 2.0
    return {"high": 4.0, "medium": 2.0, "low": 1.0}[priority]


def _reduce_priority_group(
    plan: list[dict[str, Any]],
    priority: str,
    minimum_fraction: float,
    excess_units: float,
    days: int,
) -> float:
    group = [item for item in plan if item["priority"] == priority]
    current_units = sum(item["watts"] * item["hours"] * days / 1000 for item in group)
    minimum_units = sum(
        item["watts"] * item["baseline_hours"] * minimum_fraction * days / 1000
        for item in group
    )
    reducible_units = max(0.0, current_units - minimum_units)
    reduction = min(excess_units, reducible_units)

    if current_units > 0 and reduction > 0:
        scale = (current_units - reduction) / current_units
        for item in group:
            item["hours"] = max(
                item["baseline_hours"] * minimum_fraction,
                item["hours"] * scale,
            )

    return excess_units - reduction


def generate_initial_usage_plan_data(
    year: int,
    month: int,
    max_budget_lkr: float,
    appliances: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a deterministic first-pass usage plan within the bill budget."""
    if not isinstance(appliances, list) or not appliances:
        raise ValueError("appliances must be a non-empty list")

    budget_limit = calculate_budget_unit_limit_data(year, month, max_budget_lkr)
    days = budget_limit["billing_days"]
    allowed_units = budget_limit["estimated_allowed_units"]
    plan: list[dict[str, Any]] = []

    for appliance in appliances:
        if not isinstance(appliance, dict):
            raise ValueError("each appliance must be an object with name and watts")

        name = appliance.get("name")
        watts = appliance.get("watts")
        classification = classify_appliance_priority_data(name)
        calculate_appliance_kwh_data(watts, 0, days)
        baseline_hours = _baseline_hours(
            classification["normalized_name"], classification["priority"]
        )
        plan.append(
            {
                **classification,
                "watts": float(watts),
                "baseline_hours": baseline_hours,
                "hours": baseline_hours,
            }
        )

    total_units = sum(item["watts"] * item["hours"] * days / 1000 for item in plan)
    excess_units = max(0.0, total_units - allowed_units)

    for priority, minimum_fraction in (("low", 0.0), ("medium", 0.25), ("high", 0.5)):
        excess_units = _reduce_priority_group(
            plan, priority, minimum_fraction, excess_units, days
        )

    if excess_units > 0:
        current_units = sum(item["watts"] * item["hours"] * days / 1000 for item in plan)
        scale = max(0.0, (current_units - excess_units) / current_units) if current_units else 0
        for item in plan:
            item["hours"] *= scale

    usage_items = []
    for item in plan:
        hours = math.floor((item["hours"] + 1e-9) * 100) / 100
        units = calculate_appliance_kwh_data(item["watts"], hours, days)["kwh"]
        usage_items.append(
            {
                "name": item["item_name"],
                "watts": item["watts"],
                "normalized_name": item["normalized_name"],
                "priority": item["priority"],
                "category_note": item["category_note"],
                "suggested_hours_per_day": hours,
                "estimated_monthly_units": round(units, 2),
            }
        )

    planned_units = round(sum(item["estimated_monthly_units"] for item in usage_items), 2)
    bill = calculate_domestic_bill_data(year, month, planned_units)

    return {
        "year": year,
        "month": month,
        "billing_days": days,
        "max_budget_lkr": budget_limit["max_budget_lkr"],
        "estimated_allowed_units": allowed_units,
        "appliances": usage_items,
        "total_units": planned_units,
        "estimated_bill": bill["monthly_bill"],
        "stays_within_budget": bill["monthly_bill"] <= budget_limit["max_budget_lkr"],
    }
