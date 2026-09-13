"""LangGraph workflow for the HomeWatt Advisor planner."""

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agents.appliance_agent import appliance_analyzer_node
from app.agents.bill_agent import bill_calculator_node
from app.agents.guide_agent import guide_writer_node
from app.agents.information_agent import information_node
from app.agents.optimizer_agent import usage_optimizer_node
from app.agents.response_nodes import direct_response_node, followup_advice_node
from app.agents.supervisor import supervisor_node
from app.graph.state import HomeWattState
from app.memory.session_memory import (
    append_conversation_turn,
    get_session_memory,
    save_successful_plan,
)


PLAN_SNAPSHOT_FIELDS = (
    "year",
    "month",
    "max_budget_lkr",
    "appliances",
    "appliance_priorities",
    "billing_days",
    "estimated_allowed_units",
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
    "estimated_bill",
    "stays_within_budget",
)


def _next_after_supervisor(
    state: HomeWattState,
) -> Literal[
    "appliance_analyzer",
    "followup_advice",
    "information",
    "direct_response",
]:
    intent = state.get("intent")
    if intent == "usage_plan":
        return "appliance_analyzer"
    if intent == "plan_followup":
        return "followup_advice"
    if intent in {"tariff_information", "priority_information"}:
        return "information"
    return "direct_response"


def _next_after_appliance(
    state: HomeWattState,
) -> Literal["bill_calculator", "guide_writer"]:
    if state.get("error") or state.get("casual_response"):
        return "guide_writer"
    return "bill_calculator"


def _next_after_mcp(
    state: HomeWattState,
) -> Literal["usage_optimizer", "guide_writer"]:
    if state.get("error"):
        return "guide_writer"
    return "usage_optimizer"


def _next_after_optimizer(state: HomeWattState) -> Literal["guide_writer"]:
    return "guide_writer"


def build_homewatt_graph():
    graph = StateGraph(HomeWattState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("appliance_analyzer", appliance_analyzer_node)
    graph.add_node("bill_calculator", bill_calculator_node)
    graph.add_node("usage_optimizer", usage_optimizer_node)
    graph.add_node("guide_writer", guide_writer_node)
    graph.add_node("followup_advice", followup_advice_node)
    graph.add_node("information", information_node)
    graph.add_node("direct_response", direct_response_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", _next_after_supervisor)
    graph.add_conditional_edges("appliance_analyzer", _next_after_appliance)
    graph.add_conditional_edges("bill_calculator", _next_after_mcp)
    graph.add_conditional_edges("usage_optimizer", _next_after_optimizer)
    graph.add_edge("guide_writer", END)
    graph.add_edge("followup_advice", END)
    graph.add_edge("information", END)
    graph.add_edge("direct_response", END)

    return graph.compile()


homewatt_graph = build_homewatt_graph()


def _safe_plan_snapshot(final_state: HomeWattState) -> dict[str, Any]:
    return {
        field: final_state[field]
        for field in PLAN_SNAPSHOT_FIELDS
        if field in final_state
    }


def _is_successful_plan(final_state: HomeWattState) -> bool:
    return (
        final_state.get("intent") == "usage_plan"
        and not final_state.get("error")
        and isinstance(final_state.get("usage_plan"), dict)
        and bool(final_state.get("final_answer"))
    )


async def run_homewatt_workflow(
    user_id: int,
    session_id: int | None,
    message: str,
    year: int | None = None,
    month: int | None = None,
    max_budget_lkr: float | None = None,
    appliances: list[dict[str, Any]] | None = None,
    previous_plan: dict[str, Any] | None = None,
) -> dict:
    """Run the workflow and update process-local conversation memory."""
    memory = (
        await get_session_memory(user_id, session_id)
        if session_id is not None
        else None
    )
    memory_plan = memory["last_successful_plan"] if memory else None
    initial_state: HomeWattState = {
        "user_id": user_id,
        "session_id": session_id,
        "message": message,
        "conversation_history": memory["messages"] if memory else [],
        "previous_plan": memory_plan or previous_plan,
    }
    if (
        year is not None
        and month is not None
        and max_budget_lkr is not None
        and appliances
    ):
        initial_state.update(
            {
                "structured_input": True,
                "structured_year": year,
                "structured_month": month,
                "structured_max_budget_lkr": max_budget_lkr,
                "structured_appliances": appliances,
            }
        )
    final_state = await homewatt_graph.ainvoke(initial_state)
    answer = final_state.get("final_answer", "")

    if session_id is not None:
        await append_conversation_turn(user_id, session_id, message, answer)
        if _is_successful_plan(final_state):
            await save_successful_plan(user_id, session_id, _safe_plan_snapshot(final_state))

    return {
        "answer": answer,
        "state": final_state,
        "plan_snapshot": (
            _safe_plan_snapshot(final_state)
            if _is_successful_plan(final_state)
            else None
        ),
    }
