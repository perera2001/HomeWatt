"""On-demand MCP Resource agent for tariff and priority information."""

import json
from typing import Any, Literal

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from pydantic import BaseModel

from app.agents.llm import create_chat_model, has_openai_config
from app.agents.tools import (
    read_appliance_priority_rules_tool,
    read_tariff_resource_tool,
)
from app.graph.state import HomeWattState


InformationIntent = Literal["tariff_information", "priority_information"]


class InformationResponse(BaseModel):
    answer: str


def create_information_agent(intent: InformationIntent):
    """Create an agent with only the resource tool needed for this intent."""
    if intent == "tariff_information":
        tool = read_tariff_resource_tool
        subject = "Sri Lankan domestic tariff"
    else:
        tool = read_appliance_priority_rules_tool
        subject = "household appliance-priority rules"

    return create_agent(
        model=create_chat_model(),
        tools=[tool],
        system_prompt=(
            f"Answer questions about {subject}. Call {tool.name} exactly once. "
            "Use only that MCP Resource result. Do not calculate, guess, call any "
            "other tool, or invent missing information. Keep the answer concise."
        ),
        response_format=InformationResponse,
        name="information_agent",
    )


def _parse_resource_message(message: ToolMessage) -> dict[str, Any] | None:
    if getattr(message, "status", None) == "error":
        return None
    content = message.content
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    if isinstance(content, list) and len(content) == 1:
        block = content[0]
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            try:
                parsed = json.loads(block["text"])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def _answer_from_result(result: dict[str, Any]) -> str:
    structured = result.get("structured_response")
    if isinstance(structured, InformationResponse):
        return structured.answer.strip()
    if isinstance(structured, dict) and isinstance(structured.get("answer"), str):
        return structured["answer"].strip()
    return ""


async def information_node(state: HomeWattState) -> HomeWattState:
    """Read exactly one relevant MCP Resource and return its grounded answer."""
    intent = state.get("intent")
    if intent not in {"tariff_information", "priority_information"}:
        return {**state, "final_answer": "Could not determine the information requested."}
    if not has_openai_config():
        return {
            **state,
            "final_answer": "The electricity information service is unavailable. Please try again later.",
        }

    expected_tool = (
        read_tariff_resource_tool
        if intent == "tariff_information"
        else read_appliance_priority_rules_tool
    )
    try:
        agent = create_information_agent(intent)
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": state.get("message", "")}]}
        )
    except Exception:
        return {
            **state,
            "final_answer": "Could not retrieve the requested electricity information.",
        }

    all_tool_messages = [
        message
        for message in result.get("messages", [])
        if isinstance(message, ToolMessage)
    ]
    resource_messages = [
        message for message in all_tool_messages if message.name == expected_tool.name
    ]
    if (
        len(all_tool_messages) != 1
        or len(resource_messages) != 1
        or not _parse_resource_message(resource_messages[0])
    ):
        return {
            **state,
            "final_answer": "Could not verify the requested electricity information.",
        }

    answer = _answer_from_result(result)
    return {
        **state,
        "final_answer": answer or "Could not explain the requested electricity information.",
    }
