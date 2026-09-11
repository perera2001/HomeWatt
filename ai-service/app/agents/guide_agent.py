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
    "state. Mention the user's budget, allowed units, recommended usage per "
    "appliance, total units, estimated bill, and whether the plan stays within "
    "budget. Do not perform your own tariff calculation."
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


def _format_plan_answer(state: HomeWattState) -> str:
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
        return {
            **state,
            "final_answer": (
                "I could not create a HomeWatt usage plan yet. "
                f"{state['error']} Example: My budget is Rs. 3000 for May 2026. "
                "I have TV 100W, iron 1000W and water motor 750W."
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
