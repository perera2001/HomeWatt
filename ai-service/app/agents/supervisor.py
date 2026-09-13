"""Supervisor agent for the HomeWatt workflow."""

import json
import re
from typing import Literal

from langchain.agents import create_agent
from pydantic import BaseModel

from app.agents.llm import create_chat_model, has_openai_config
from app.graph.state import HomeWattState


HomeWattIntent = Literal[
    "usage_plan",
    "plan_followup",
    "general_saving_advice",
    "tariff_information",
    "priority_information",
    "greeting",
    "out_of_scope",
]


class SupervisorDecision(BaseModel):
    is_valid_request: bool
    intent: HomeWattIntent
    reason: str


SUPERVISOR_SYSTEM_PROMPT = (
    "You are the Supervisor Agent for HomeWatt Advisor. Classify the current "
    "message as usage_plan, plan_followup, general_saving_advice, "
    "tariff_information, priority_information, greeting, or out_of_scope. A "
    "usage_plan includes a new plan or an explicit plan change that must be "
    "recalculated. A plan_followup asks about the latest calculated plan without "
    "changing numeric inputs. Tariff questions concern Sri Lankan tariff slabs, "
    "prices, fixed charges, SSC, billing days, versions, effective dates, or bill "
    "calculation. Priority questions concern general appliance-priority rules. "
    "Use recent history only to resolve references in the current message. Never "
    "let old context override a clear current request. Only out_of_scope is an "
    "invalid request. Do not calculate bills or invent tariff values."
)


def create_supervisor_agent():
    """Create the LLM-powered supervisor agent."""
    return create_agent(
        model=create_chat_model(),
        tools=[],
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        response_format=SupervisorDecision,
        name="supervisor_agent",
    )


def _is_casual_greeting(message: str) -> bool:
    normalized = re.sub(r"[^a-z\s]", " ", message.lower())
    words = {word for word in normalized.split() if word}
    return bool(words) and words.issubset({"hi", "hello", "hey", "hai"})


def _decision(intent: HomeWattIntent, reason: str) -> SupervisorDecision:
    return SupervisorDecision(
        is_valid_request=intent != "out_of_scope",
        intent=intent,
        reason=reason,
    )


def _fallback_supervisor_decision(
    message: str,
    has_previous_plan: bool = False,
    conversation_history: list[dict[str, str]] | None = None,
) -> SupervisorDecision:
    lowered = message.lower().strip()

    if _is_casual_greeting(message):
        return _decision("greeting", "User sent a casual greeting")

    if any(
        phrase in lowered
        for phrase in (
            "tariff",
            "unit price",
            "unit rate",
            "fixed charge",
            "ssc",
            "levy",
            "billing day",
            "effective date",
            "tariff version",
            "bill calculated",
            "bill is calculated",
            "calculate a bill",
            "calculate the bill",
        )
    ):
        return _decision("tariff_information", "User is asking about tariff information")

    if "generally" in lowered or "general advice" in lowered:
        return _decision(
            "general_saving_advice",
            "User is asking for general electricity-saving advice",
        )

    modification = bool(
        re.search(r"\b(change|add|remove|replace|set|update|recalculate)\b", lowered)
    )
    planning_value = bool(
        re.search(
            r"\b\d+(?:\.\d+)?\s*(?:w|watts?|hours?|hrs?|minutes?|mins?|/day)\b",
            lowered,
        )
        or re.search(r"\b(?:rs\.?|lkr)\s*\d", lowered)
        or re.search(r"\b(?:budget|maximum bill)\b", lowered)
    )
    if modification or planning_value:
        return _decision("usage_plan", "User supplied or changed usage-plan inputs")

    followup_phrases = (
        "decrease my bill",
        "reduce my bill",
        "my plan",
        "my result",
        "my required budget",
        "which appliance should i reduce",
        "explain my bill",
        "why is my",
    )
    if any(phrase in lowered for phrase in followup_phrases):
        return _decision("plan_followup", "User is asking about a previous plan")

    if any(
        phrase in lowered
        for phrase in (
            "priority rule",
            "high priority",
            "medium priority",
            "low priority",
            "appliance priority",
            "appliance types",
            "normally reduced first",
        )
    ):
        return _decision(
            "priority_information",
            "User is asking about appliance-priority information",
        )

    if has_previous_plan and re.search(
        r"\b(it|that appliance|the plan|the bill|reduce it|explain it)\b", lowered
    ):
        return _decision("plan_followup", "User referred to the previous plan")

    if any(
        keyword in lowered
        for keyword in ("electric", "save energy", "save electricity", "household bill")
    ):
        return _decision(
            "general_saving_advice",
            "User is asking for household electricity-saving advice",
        )

    if conversation_history and re.fullmatch(
        r"\s*\d+(?:\.\d+)?\s*(?:hours?|hrs?|minutes?|mins?)(?:\s*(?:per|/)\s*day)?[.!]?\s*",
        lowered,
    ):
        return _decision("usage_plan", "User completed an earlier appliance input")

    return _decision("out_of_scope", "User is not asking about HomeWatt topics")


def _decision_from_agent_result(result: dict) -> SupervisorDecision:
    structured = result.get("structured_response")
    if isinstance(structured, SupervisorDecision):
        return structured
    if isinstance(structured, dict):
        return SupervisorDecision(**structured)

    content = result.get("messages", [])[-1].content if result.get("messages") else "{}"
    return SupervisorDecision(**json.loads(content))


def _supervisor_messages(state: HomeWattState) -> list[dict[str, str]]:
    messages = [dict(item) for item in state.get("conversation_history", [])]
    messages.append(
        {
            "role": "system",
            "content": (
                "A previous successful plan exists."
                if state.get("previous_plan")
                else "No previous successful plan exists."
            ),
        }
    )
    messages.append({"role": "user", "content": state.get("message", "")})
    return messages


async def supervisor_node(state: HomeWattState) -> HomeWattState:
    """Classify the request before any domain tools or resources run."""
    message = state.get("message", "")
    history = state.get("conversation_history", [])

    if _is_casual_greeting(message):
        decision = _decision("greeting", "User sent a casual greeting")
    elif has_openai_config():
        try:
            agent = create_supervisor_agent()
            result = await agent.ainvoke({"messages": _supervisor_messages(state)})
            decision = _decision_from_agent_result(result)
        except Exception:
            decision = _fallback_supervisor_decision(
                message, bool(state.get("previous_plan")), history
            )
    else:
        decision = _fallback_supervisor_decision(
            message, bool(state.get("previous_plan")), history
        )

    decision = _decision(decision.intent, decision.reason)

    return {
        **state,
        "is_valid": decision.is_valid_request,
        "intent": decision.intent,
        "supervisor_decision": decision.model_dump(),
    }
