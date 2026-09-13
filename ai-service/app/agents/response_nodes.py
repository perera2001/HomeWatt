"""Small terminal response nodes for non-calculation intents."""

from typing import Any

from app.graph.state import HomeWattState


CREATE_PLAN_MESSAGE = (
    "Please create a usage plan first by providing the year, month, maximum "
    "budget, and each appliance's watts and required hours per day."
)


def _number(value: Any) -> str:
    return f"{float(value):g}" if isinstance(value, (int, float)) else "unknown"


def _followup_answer(plan: dict[str, Any]) -> str:
    requested_items = plan.get("requested_plan", {}).get("appliances", [])
    affordable_items = (plan.get("affordable_plan") or {}).get("appliances", [])
    suggested_by_name = {
        str(item.get("normalized_name", item.get("name", ""))).casefold(): item
        for item in affordable_items
    }

    lines = [
        "Based on your latest successful plan:",
        f"Estimated bill: Rs. {_number(plan.get('estimated_bill'))}.",
    ]
    for item in requested_items:
        key = str(item.get("normalized_name", item.get("name", ""))).casefold()
        suggested = suggested_by_name.get(key, item)
        suggested_hours = suggested.get(
            "suggested_hours_per_day", item.get("required_hours_per_day")
        )
        lines.append(
            f"- {item.get('name')}: {_number(item.get('required_hours_per_day'))} "
            f"required hours/day; {_number(suggested_hours)} suggested hours/day "
            f"({item.get('priority', 'medium')} priority)."
        )

    low_names = [
        str(item.get("name"))
        for item in requested_items
        if item.get("priority") == "low"
    ]
    high_names = [
        str(item.get("name"))
        for item in requested_items
        if item.get("priority") == "high"
    ]
    if low_names:
        lines.append("Reduce unnecessary " + ", ".join(low_names) + " usage first.")
    else:
        lines.append("Reduce non-essential or medium-priority usage first.")
    if high_names:
        lines.append("Protect reasonable " + ", ".join(high_names) + " usage.")
    return "\n".join(lines)


async def direct_response_node(state: HomeWattState) -> HomeWattState:
    """Return a tool-free response for simple intents."""
    intent = state.get("intent")
    if intent == "greeting":
        answer = "Hi, how can I assist you today?"
    elif intent == "form_required":
        answer = (
            "To calculate a usage plan, add your appliances in the table first. "
            "After the plan is created, use chat to ask questions about that plan."
        )
    elif intent == "general_saving_advice":
        answer = (
            "Switch off unused lights and devices, avoid standby power, use "
            "high-wattage appliances for shorter periods, and run full laundry "
            "loads. This is general advice, not a personalized usage plan."
        )
    else:
        answer = (
            "I can help with Sri Lankan domestic electricity tariffs, bill "
            "calculations, appliance priorities and household usage planning."
        )
    return {**state, "final_answer": answer}


async def followup_advice_node(state: HomeWattState) -> HomeWattState:
    """Answer from the latest authoritative plan without recalculating it."""
    previous_plan = state.get("previous_plan")
    answer = _followup_answer(previous_plan) if previous_plan else CREATE_PLAN_MESSAGE
    return {**state, "final_answer": answer}
