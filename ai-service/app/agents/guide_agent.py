"""Rule-based guide writer for final user-facing answers."""

import calendar

from app.graph.state import HomeWattState


def _money(value: float) -> str:
    return f"Rs. {value:,.2f}"


async def guide_writer_node(state: HomeWattState) -> HomeWattState:
    """Create a readable answer from workflow state without calling an LLM."""
    if state.get("error"):
        return {
            **state,
            "final_answer": (
                "I could not create a HomeWatt usage plan yet. "
                f"{state['error']} Example: My budget is Rs. 3000 for May 2026. "
                "I have TV 100W, iron 1000W and water motor 750W."
            ),
        }

    month_name = calendar.month_name[state["month"]]
    usage_plan = state.get("usage_plan", {})
    appliances = usage_plan.get("appliances", [])

    lines = [
        f"Your HomeWatt Advisor usage plan for {month_name} {state['year']}:",
        (
            f"Your budget is {_money(state['max_budget_lkr'])}. "
            f"Estimated allowed units are around {state['estimated_allowed_units']} kWh."
        ),
        "Recommended usage:",
    ]

    for item in appliances:
        lines.append(
            "- "
            f"{item['name']} ({item['watts']:g}W): "
            f"{item['suggested_hours_per_day']:g} hours/day, "
            f"about {item['estimated_monthly_units']:g} units/month "
            f"({item['priority']} priority)."
        )

    lines.extend(
        [
            f"Total estimated units: {state['total_units']} kWh.",
            f"Estimated bill: {_money(state['estimated_bill'])}.",
        ]
    )

    if state["stays_within_budget"]:
        lines.append("This plan stays within your budget.")
    else:
        lines.append("This plan is above your budget, so reduce low-priority usage first.")

    lines.append(
        "Practical advice: batch high-wattage appliance use, avoid unnecessary entertainment "
        "loads, and protect essential water and cooling needs first."
    )

    return {
        **state,
        "final_answer": "\n".join(lines),
    }
