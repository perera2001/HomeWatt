"""Shared state for the HomeWatt Advisor LangGraph workflow."""

from typing import Any, TypedDict


class HomeWattState(TypedDict, total=False):
    user_id: int
    session_id: int | None
    message: str

    is_valid: bool
    intent: str
    casual_response: str
    supervisor_decision: dict[str, Any]
    year: int
    month: int
    max_budget_lkr: float
    appliances: list[dict[str, Any]]
    appliance_priorities: list[dict[str, Any]]
    priority_rules_resource: dict[str, Any]

    billing_days: int
    estimated_allowed_units: float
    estimated_bill_at_limit: float
    budget_limit_result: dict[str, Any]
    tariff_resource: dict[str, Any]

    usage_plan: dict[str, Any]
    requested_plan: dict[str, Any]
    affordable_plan: dict[str, Any] | None
    requested_total_units: float
    minimum_required_budget: float
    minimum_possible_bill: float
    budget_shortfall: float
    remaining_budget: float
    requirements_met: bool
    adjustments_required: bool
    budget_feasible: bool
    total_units: float
    estimated_bill: float
    stays_within_budget: bool

    final_answer: str
    error: str
