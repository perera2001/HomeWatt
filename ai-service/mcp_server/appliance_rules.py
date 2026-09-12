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


def _reduce_priority_group(
    plan: list[dict[str, Any]],
    priority: str,
    excess_units: float,
    days: int,
) -> float:
    group = [item for item in plan if item["priority"] == priority]
    current_units = sum(
        item["watts"] * item["suggested_hours_per_day"] * days / 1000
        for item in group
    )
    reduction = min(excess_units, current_units)

    if current_units > 0 and reduction > 0:
        # Appliances in the same priority group are reduced proportionally.
        scale = (current_units - reduction) / current_units
        for item in group:
            item["suggested_hours_per_day"] = max(
                0.0,
                item["suggested_hours_per_day"] * scale,
            )

    return excess_units - reduction


def _floor_hours(hours: float) -> float:
    """Floor hours to four decimals so display rounding cannot add energy."""
    return math.floor((hours + 1e-12) * 10000) / 10000


def _make_affordable_items(
    requested_items: list[dict[str, Any]],
    target_units: float,
    days: int,
) -> list[dict[str, Any]]:
    plan = [
        {
            **item,
            "suggested_hours_per_day": item["required_hours_per_day"],
        }
        for item in requested_items
    ]
    requested_total_units = round(
        sum(item["requested_monthly_units"] for item in requested_items), 2
    )
    excess_units = max(0.0, requested_total_units - target_units)

    for priority in ("low", "medium", "high"):
        excess_units = _reduce_priority_group(plan, priority, excess_units, days)

    affordable_items = []
    for item in plan:
        suggested_hours = _floor_hours(item["suggested_hours_per_day"])
        estimated_units = calculate_appliance_kwh_data(
            item["watts"], suggested_hours, days
        )["kwh"]
        affordable_items.append(
            {
                "name": item["name"],
                "watts": item["watts"],
                "normalized_name": item["normalized_name"],
                "priority": item["priority"],
                "category_note": item["category_note"],
                "required_hours_per_day": item["required_hours_per_day"],
                "suggested_hours_per_day": suggested_hours,
                "requested_monthly_units": item["requested_monthly_units"],
                "estimated_monthly_units": estimated_units,
                "requirement_met": (
                    suggested_hours + 1e-9 >= item["required_hours_per_day"]
                ),
                "hours_reduced_per_day": round(
                    max(0.0, item["required_hours_per_day"] - suggested_hours), 4
                ),
            }
        )
    return affordable_items


def generate_initial_usage_plan_data(
    year: int,
    month: int,
    max_budget_lkr: float,
    appliances: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare requested usage with the budget and create an affordable plan."""
    if not isinstance(appliances, list) or not appliances:
        raise ValueError("appliances must be a non-empty list")

    budget_limit = calculate_budget_unit_limit_data(year, month, max_budget_lkr)
    days = budget_limit["billing_days"]
    allowed_units = float(budget_limit["estimated_allowed_units"])
    requested_items: list[dict[str, Any]] = []

    for appliance in appliances:
        if not isinstance(appliance, dict):
            raise ValueError(
                "each appliance must contain name, watts, and required_hours_per_day"
            )

        name = appliance.get("name")
        watts = appliance.get("watts")
        required_hours = appliance.get("required_hours_per_day")
        classification = classify_appliance_priority_data(name)
        if required_hours is None:
            raise ValueError(f"required_hours_per_day is required for {name}")
        if isinstance(required_hours, bool) or not isinstance(required_hours, (int, float)):
            raise ValueError(f"required_hours_per_day must be a number for {name}")
        required_hours = float(required_hours)
        if not math.isfinite(required_hours) or required_hours <= 0:
            raise ValueError(f"required_hours_per_day must be greater than 0 for {name}")
        if required_hours > 24:
            raise ValueError(f"required_hours_per_day must not exceed 24 for {name}")

        requested_units = calculate_appliance_kwh_data(
            watts, required_hours, days
        )["kwh"]
        requested_items.append(
            {
                "name": classification["item_name"],
                "watts": float(watts),
                "normalized_name": classification["normalized_name"],
                "priority": classification["priority"],
                "category_note": classification["category_note"],
                "required_hours_per_day": required_hours,
                "requested_monthly_units": requested_units,
            }
        )

    requested_total_units = round(
        sum(item["requested_monthly_units"] for item in requested_items), 2
    )
    requested_bill = calculate_domestic_bill_data(year, month, requested_total_units)
    minimum_required_budget = requested_bill["monthly_bill"]
    minimum_possible_bill = calculate_domestic_bill_data(year, month, 0)["monthly_bill"]
    budget = float(budget_limit["max_budget_lkr"])
    budget_shortfall = round(max(0.0, minimum_required_budget - budget), 2)
    remaining_budget = round(max(0.0, budget - minimum_required_budget), 2)
    budget_feasible = budget >= minimum_possible_bill
    requirements_met = budget_feasible and minimum_required_budget <= budget
    adjustments_required = budget_feasible and not requirements_met

    requested_plan = {
        "appliances": requested_items,
        "total_units": requested_total_units,
        "estimated_bill": minimum_required_budget,
        "bill_breakdown": requested_bill,
    }

    affordable_plan = None
    usage_items: list[dict[str, Any]] = []
    total_units = 0.0
    estimated_bill = minimum_possible_bill

    if budget_feasible:
        target_units = requested_total_units if requirements_met else allowed_units
        usage_items = _make_affordable_items(requested_items, target_units, days)
        total_units = round(
            sum(item["estimated_monthly_units"] for item in usage_items), 2
        )
        bill = calculate_domestic_bill_data(year, month, total_units)

        # A two-decimal unit round-up or tariff boundary must never exceed budget.
        while bill["monthly_bill"] > budget and target_units > 0:
            target_units = max(0.0, round(target_units - 0.01, 2))
            usage_items = _make_affordable_items(requested_items, target_units, days)
            total_units = round(
                sum(item["estimated_monthly_units"] for item in usage_items), 2
            )
            bill = calculate_domestic_bill_data(year, month, total_units)

        estimated_bill = bill["monthly_bill"]
        affordable_plan = {
            "appliances": usage_items,
            "total_units": total_units,
            "estimated_bill": estimated_bill,
            "bill_breakdown": bill,
            "stays_within_budget": estimated_bill <= budget,
        }

    return {
        "year": year,
        "month": month,
        "billing_days": days,
        "max_budget_lkr": budget,
        "estimated_allowed_units": allowed_units,
        "requested_plan": requested_plan,
        "affordable_plan": affordable_plan,
        "requested_total_units": requested_total_units,
        "minimum_required_budget": minimum_required_budget,
        "minimum_possible_bill": minimum_possible_bill,
        "budget_shortfall": budget_shortfall,
        "remaining_budget": remaining_budget,
        "requirements_met": requirements_met,
        "adjustments_required": adjustments_required,
        "budget_feasible": budget_feasible,
        "appliances": usage_items,
        "total_units": total_units,
        "estimated_bill": estimated_bill,
        "stays_within_budget": bool(
            affordable_plan and affordable_plan["stays_within_budget"]
        ),
    }
