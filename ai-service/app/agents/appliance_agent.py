"""Structured appliance input node."""

import re
from typing import Any

from app.graph.state import HomeWattState


STRUCTURED_PLAN_REQUIRED_MESSAGE = (
    "To calculate a usage plan, add your appliances in the table first. "
    "After the plan is created, use chat to ask questions about that plan."
)


def _normalize_reference_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).lower())).strip()


def _structured_priority_result(appliance: dict[str, Any]) -> dict[str, str]:
    name = str(appliance["name"]).strip()
    normalized_name = _normalize_reference_text(name)
    priority = appliance["priority"]
    notes = {
        "high": "User marked this appliance as high priority.",
        "medium": "User marked this appliance as medium priority.",
        "low": "User marked this appliance as low priority.",
    }
    return {
        "item_name": name,
        "normalized_name": normalized_name,
        "priority": priority,
        "category_note": notes[priority],
    }


def _structured_input_state(state: HomeWattState) -> HomeWattState:
    appliances = [
        {
            "name": str(appliance["name"]).strip(),
            "watts": float(appliance["watts"]),
            "required_hours_per_day": float(appliance["required_hours_per_day"]),
            "priority": appliance["priority"],
        }
        for appliance in state["structured_appliances"]
    ]
    return {
        **state,
        "year": state["structured_year"],
        "month": state["structured_month"],
        "max_budget_lkr": state["structured_max_budget_lkr"],
        "appliances": appliances,
        "appliance_priorities": [
            _structured_priority_result(appliance) for appliance in appliances
        ],
    }


async def appliance_analyzer_node(state: HomeWattState) -> HomeWattState:
    """Accept only structured appliance input for plan creation."""
    if state.get("structured_input"):
        return _structured_input_state(state)

    return {
        **state,
        "error": STRUCTURED_PLAN_REQUIRED_MESSAGE,
    }
