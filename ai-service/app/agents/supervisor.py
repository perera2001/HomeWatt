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
    "form_required",
    "greeting",
    "out_of_scope",
]


class SupervisorDecision(BaseModel):
    is_valid_request: bool
    intent: HomeWattIntent
    reason: str


SUPERVISOR_SYSTEM_PROMPT = (
    "You are the Supervisor Agent for HomeWatt Advisor. Classify the current "
    "message as plan_followup, general_saving_advice, tariff_information, "
    "priority_information, greeting, or out_of_scope. Usage plans are created "
    "only from structured form inputs, not from free-text chat. A plan_followup "
    "asks about the latest calculated plan without "
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

    if _is_planning_text(message):
        return _decision("form_required", "Usage plans require structured form inputs")

    followup_phrases = (
        "decrease my bill",
        "reduce my bill",
        "reduce this bill",
        "my plan",
        "latest plan",
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

    return _decision("out_of_scope", "User is not asking about HomeWatt topics")


def _is_planning_text(message: str) -> bool:
    lowered = message.lower().strip()
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
    return modification or planning_value


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

    if state.get("structured_input"):
        decision = _decision("usage_plan", "User supplied structured usage-plan inputs")
    elif _is_casual_greeting(message):
        decision = _decision("greeting", "User sent a casual greeting")
    elif _is_planning_text(message):
        decision = _decision("form_required", "Usage plans require structured form inputs")
    else:
        fallback_decision = _fallback_supervisor_decision(
            message, bool(state.get("previous_plan")), history
        )
        if fallback_decision.intent != "out_of_scope":
            decision = fallback_decision
        elif has_openai_config():
            try:
                agent = create_supervisor_agent()
                result = await agent.ainvoke({"messages": _supervisor_messages(state)})
                decision = _decision_from_agent_result(result)
            except Exception:
                decision = fallback_decision
        else:
            decision = fallback_decision

    if not state.get("structured_input") and decision.intent == "usage_plan":
        decision = _decision("form_required", "Usage plans require structured form inputs")
    else:
        decision = _decision(decision.intent, decision.reason)

    return {
        **state,
        "is_valid": decision.is_valid_request,
        "intent": decision.intent,
        "supervisor_decision": decision.model_dump(),
    }
