"""Supervisor agent for the HomeWatt workflow."""

import json
import re

from langchain.agents import create_agent
from langchain_core.tools import tool
from pydantic import BaseModel

from app.agents.llm import create_chat_model, has_openai_config
from app.graph.state import HomeWattState


class SupervisorDecision(BaseModel):
    is_valid_request: bool
    reason: str


SUPERVISOR_SYSTEM_PROMPT = (
    "You are the Supervisor Agent for HomeWatt Advisor. Your job is to decide "
    "whether the user is asking for a Sri Lankan home electricity usage plan. "
    "If the request includes electricity bill budget, appliances, watts, usage "
    "planning, or bill control, mark it as valid. Do not calculate bills. Do "
    "not invent tariff values."
)


@tool
def detect_homewatt_intent(message: str) -> dict:
    """Detect whether a message is about HomeWatt electricity planning."""
    lowered = message.lower()
    keywords = [
        "electric",
        "bill",
        "budget",
        "watt",
        "usage",
        "unit",
        "appliance",
        "kwh",
    ]
    is_valid = any(keyword in lowered for keyword in keywords)
    return {
        "is_valid_request": is_valid,
        "reason": (
            "User is asking for electricity usage planning"
            if is_valid
            else "User is not asking for electricity usage planning"
        ),
    }


def create_supervisor_agent():
    """Create the LLM-powered supervisor agent."""
    return create_agent(
        model=create_chat_model(),
        tools=[detect_homewatt_intent],
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        response_format=SupervisorDecision,
        name="supervisor_agent",
    )


def _is_casual_greeting(message: str) -> bool:
    normalized = re.sub(r"[^a-z\s]", " ", message.lower())
    words = {word for word in normalized.split() if word}
    return bool(words) and words.issubset({"hi", "hello", "hey", "hai"})


def _fallback_supervisor_decision(message: str) -> SupervisorDecision:
    if _is_casual_greeting(message):
        return SupervisorDecision(
            is_valid_request=True,
            reason="User sent a casual greeting",
        )

    detection = detect_homewatt_intent.invoke({"message": message})
    return SupervisorDecision(**detection)


def _decision_from_agent_result(result: dict) -> SupervisorDecision:
    structured = result.get("structured_response")
    if isinstance(structured, SupervisorDecision):
        return structured
    if isinstance(structured, dict):
        return SupervisorDecision(**structured)

    content = result.get("messages", [])[-1].content if result.get("messages") else "{}"
    try:
        return SupervisorDecision(**json.loads(content))
    except (json.JSONDecodeError, TypeError, ValueError):
        return SupervisorDecision(
            is_valid_request=False,
            reason="Could not understand whether this is an electricity planning request",
        )


async def supervisor_node(state: HomeWattState) -> HomeWattState:
    """Decide whether the workflow should continue."""
    message = state.get("message", "")

    if _is_casual_greeting(message):
        decision = SupervisorDecision(
            is_valid_request=True,
            reason="User sent a casual greeting",
        )
    elif has_openai_config():
        try:
            agent = create_supervisor_agent()
            result = await agent.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": message,
                        }
                    ]
                }
            )
            decision = _decision_from_agent_result(result)
        except Exception:
            decision = _fallback_supervisor_decision(message)
    else:
        decision = _fallback_supervisor_decision(message)

    if not decision.is_valid_request:
        return {
            **state,
            "is_valid": False,
            "supervisor_decision": decision.model_dump(),
            "error": (
                "I can help with Sri Lankan home electricity usage planning, "
                "bill budgets, appliances, watts, and usage control."
            ),
        }

    return {
        **state,
        "is_valid": True,
        "supervisor_decision": decision.model_dump(),
    }
