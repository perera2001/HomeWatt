"""Guide writer agent for final user-facing answers."""

import calendar

from langchain.agents import create_agent
from pydantic import BaseModel

from app.agents.llm import create_chat_model, has_openai_config
from app.agents.tools import (
    dumps_for_prompt,
    get_bill_breakdown_prompt_tool,
    get_usage_guide_prompt_tool,
)
from app.graph.state import HomeWattState


class GuideWriterResponse(BaseModel):
    answer: str


GUIDE_WRITER_SYSTEM_PROMPT = (
    "You are the Guide Writer Agent for HomeWatt Advisor. Write a clear "
    "electricity usage guide using only the calculated MCP tool results in the "
    "state. Distinguish required requested hours from suggested affordable "
    "hours. Never change numbers, calculate a tariff, or claim requirements "
    "were met after hours were reduced. Clearly state when the budget is below "
    "the minimum zero-unit bill. Do not invent appliances or values. End each "
    "successful plan with a short practical electricity-saving instruction."
)


def create_guide_writer_agent():
    """Create the LLM-powered guide writer agent."""
    return create_agent(
        model=create_chat_model(),
        tools=[get_usage_guide_prompt_tool, get_bill_breakdown_prompt_tool],
        system_prompt=GUIDE_WRITER_SYSTEM_PROMPT,
        response_format=GuideWriterResponse,
        name="guide_writer_agent",
    )


def _money(value: float) -> str:
    return f"Rs. {value:,.2f}"


def _saving_instruction(state: HomeWattState) -> str:
    names = {
        item.get("normalized_name", item.get("name", "").lower())
        for item in state.get("requested_plan", {}).get("appliances", [])
    }
    if any("iron" in name for name in names) and any("tv" in name for name in names):
        return (
            "To reduce your bill, batch ironing into fewer sessions and reduce "
            "unnecessary TV usage before reducing essential appliance use."
        )
    return (
        "To reduce your bill, reduce low-priority appliance use first and switch "
        "devices off instead of leaving them on standby."
    )


def _format_plan_answer(state: HomeWattState) -> str:
    month_name = calendar.month_name[state["month"]]
    requested_plan = state.get("requested_plan", {})
    requested_items = requested_plan.get("appliances", [])

    lines = [
        f"Your HomeWatt Advisor usage plan for {month_name} {state['year']}:",
        f"Maximum budget: {_money(state['max_budget_lkr'])}",
        f"Minimum budget required for requested usage: {_money(state['minimum_required_budget'])}",
    ]

    if not state["budget_feasible"]:
        lines.extend(
            [
                f"Minimum possible bill, even at zero units: {_money(state['minimum_possible_bill'])}",
                f"Budget shortfall for your requirements: {_money(state['budget_shortfall'])}",
                "",
                (
                    "No electricity usage plan can remain within "
                    f"{_money(state['max_budget_lkr'])} under the current tariff because "
                    "the fixed charge and SSC levy already exceed the budget."
                ),
                (
                    "Increase the budget above the minimum possible bill and reduce "
                    "non-essential appliance usage first."
                ),
            ]
        )
        return "\n".join(lines)

    if state["requirements_met"]:
        lines.extend([f"Remaining budget: {_money(state['remaining_budget'])}", "Requested usage:"])
        for item in requested_items:
            lines.append(
                f"- {item['name']} ({item['watts']:g}W): "
                f"{item['required_hours_per_day']:g} required hours/day, "
                f"{item['requested_monthly_units']:.2f} kWh/month."
            )
        lines.extend(
            [
                f"Total units: {state['total_units']:g} kWh.",
                f"Estimated bill: {_money(state['estimated_bill'])}.",
                "All requested usage requirements are satisfied.",
                _saving_instruction(state),
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            f"Budget shortfall for requested usage: {_money(state['budget_shortfall'])}",
            "The exact requested usage exceeds your budget, so adjustments are required.",
            "Requested hours -> suggested affordable hours:",
        ]
    )
    affordable_items = state.get("affordable_plan", {}).get("appliances", [])
    for item in affordable_items:
        change = "reduced" if not item["requirement_met"] else "unchanged"
        lines.append(
            f"- {item['name']} ({item['watts']:g}W, {item['priority']} priority): "
            f"{item['required_hours_per_day']:g} -> {item['suggested_hours_per_day']:g} "
            f"hours/day ({change}), {item['estimated_monthly_units']:.2f} kWh/month."
        )

    lines.extend(
        [
            f"Adjusted total units: {state['total_units']:g} kWh.",
            f"Adjusted estimated bill: {_money(state['estimated_bill'])}.",
            "The adjusted plan stays within budget, but not all original requirements are satisfied.",
            _saving_instruction(state),
        ]
    )

    return "\n".join(lines)


def _agent_answer_from_result(result: dict) -> str:
    structured = result.get("structured_response")
    if isinstance(structured, GuideWriterResponse):
        return structured.answer
    if isinstance(structured, dict) and structured.get("answer"):
        return structured["answer"]
    if result.get("messages"):
        return result["messages"][-1].content
    return ""


async def _write_answer_with_agent(state: HomeWattState) -> str:
    usage_plan = state.get("usage_plan", {})
    budget_limit_result = state.get("budget_limit_result", {})
    bill_breakdown = {
        "budget_limit_result": budget_limit_result,
        "estimated_bill": state.get("estimated_bill"),
        "total_units": state.get("total_units"),
        "stays_within_budget": state.get("stays_within_budget"),
    }

    grounded_prompt = await get_usage_guide_prompt_tool.ainvoke(
        {
            "year": state["year"],
            "month": state["month"],
            "max_budget_lkr": state["max_budget_lkr"],
            "appliances_json": dumps_for_prompt(state.get("appliances", [])),
            "usage_plan_json": dumps_for_prompt(usage_plan),
            "bill_breakdown_json": dumps_for_prompt(bill_breakdown),
        }
    )

    agent = create_guide_writer_agent()
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"{grounded_prompt}\n\n"
                        "Use this final workflow state. Do not change any numbers:\n"
                        f"{dumps_for_prompt(state)}"
                    ),
                }
            ]
        }
    )
    return _agent_answer_from_result(result)


async def guide_writer_node(state: HomeWattState) -> HomeWattState:
    """Create a readable answer from workflow state."""
    if state.get("casual_response"):
        return {
            **state,
            "final_answer": state["casual_response"],
        }

    if state.get("error"):
        if state["error"].startswith("Please enter"):
            return {
                **state,
                "final_answer": state["error"],
            }

        example = ""
        if "Example:" not in state["error"]:
            example = (
                " Example: My budget is Rs. 3000 for May 2026. I need TV 100W "
                "for 2 hours/day, iron 1000W for 15 minutes/day, and water motor "
                "750W for 1.5 hours/day."
            )
        return {
            **state,
            "final_answer": (
                "I could not create a HomeWatt usage plan yet. "
                f"{state['error']}{example}"
            ),
        }

    if has_openai_config():
        try:
            answer = await _write_answer_with_agent(state)
            if answer:
                return {
                    **state,
                    "final_answer": answer,
                }
        except Exception:
            pass

    return {
        **state,
        "final_answer": _format_plan_answer(state),
    }
