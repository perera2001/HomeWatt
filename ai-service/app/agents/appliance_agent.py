"""Appliance analyzer agent."""

import json
import re
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage
from pydantic import BaseModel, Field

from app.agents.llm import create_chat_model, has_openai_config
from app.agents.tools import (
    classify_appliance_priority_tool,
    validate_appliance_input_tool,
)
from app.graph.state import HomeWattState


MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

GREETING_WORDS = {"hi", "hello", "hey", "hai"}


class ExtractedAppliance(BaseModel):
    name: str
    watts: float
    required_hours_per_day: float


class ApplianceExtraction(BaseModel):
    year: int | None = None
    month: int | None = None
    max_budget_lkr: float | None = None
    appliances: list[ExtractedAppliance] = Field(default_factory=list)
    error: str | None = None


APPLIANCE_ANALYZER_SYSTEM_PROMPT = (
    "You are the Appliance Analyzer Agent for HomeWatt Advisor. Extract year, "
    "month, maximum budget in LKR, and each appliance's name, watts, and "
    "required_hours_per_day from the user's message. Accept hours per day, "
    "hours/day, daily for N hours, and convert daily minutes to hours. Do not "
    "calculate electricity bills. Never guess missing watts or required hours. "
    "Required hours must be greater than 0 and no more than 24. Never invent "
    "validation results, appliance priorities, normalized names, category notes, "
    "or priority rules. For every planning request, you must follow this exact "
    "sequence: (1) extract all fields, (2) call validate_appliance_input_tool "
    "exactly once with all extracted appliances encoded as JSON, (3) if validation "
    "fails, stop and return the validation error, (4) call "
    "classify_appliance_priority_tool exactly once for each extracted appliance, "
    "using its original name, and (5) produce the final structured response. "
    "Recent messages and a previous-plan summary may be provided for follow-up "
    "input. Use only explicit relevant values from that context. Current explicit "
    "values override previous values, and a clearly new plan must not inherit an "
    "unrelated old plan. Tool results are authoritative. Do not skip, repeat, or "
    "replace these calls."
)


def create_appliance_analyzer_agent():
    """Create the LLM-powered appliance analyzer agent."""
    return create_agent(
        model=create_chat_model(),
        tools=[
            validate_appliance_input_tool,
            classify_appliance_priority_tool,
        ],
        system_prompt=APPLIANCE_ANALYZER_SYSTEM_PROMPT,
        response_format=ApplianceExtraction,
        name="appliance_analyzer_agent",
    )


def _is_greeting(message: str) -> bool:
    normalized = re.sub(r"[^a-z\s]", " ", message.lower())
    words = {word for word in normalized.split() if word}
    return bool(words) and words.issubset(GREETING_WORDS)


def _extract_month_year(message: str) -> tuple[int | None, int | None]:
    month_pattern = "|".join(sorted(MONTHS, key=len, reverse=True))
    match = re.search(rf"\b({month_pattern})\b\s+(\d{{4}})", message, re.IGNORECASE)
    if match:
        return MONTHS[match.group(1).lower()], int(match.group(2))

    match = re.search(rf"\b(\d{{4}})\s+({month_pattern})\b", message, re.IGNORECASE)
    if match:
        return MONTHS[match.group(2).lower()], int(match.group(1))

    return None, None


def _extract_budget(message: str) -> float | None:
    patterns = [
        r"\b(?:rs\.?|lkr)\s*([\d,]+(?:\.\d+)?)",
        r"\bbudget\s*(?:is|of|=|:)?\s*(?:rs\.?|lkr)?\s*([\d,]+(?:\.\d+)?)",
        r"\bmaximum\s+bill\s*(?:is|of|=|:)?\s*(?:rs\.?|lkr)?\s*([\d,]+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def _clean_appliance_name(name: str) -> str:
    cleaned = re.sub(
        r"^(?:(?:and|with|i\s+have|we\s+have|have|has|a|an|the|"
        r"i\s+need\s+to\s+use|i\s+need|use|need)\s+)+",
        "",
        name.strip(),
        flags=re.I,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" .,-:")


def _extract_appliances(message: str) -> list[dict[str, Any]]:
    appliance_pattern = re.compile(
        r"([a-zA-Z][a-zA-Z ]*?)\s+(-?\d+(?:\.\d+)?)\s*(?:w|watts)\b",
        re.IGNORECASE,
    )
    matches = list(appliance_pattern.finditer(message))
    appliances = []
    for index, match in enumerate(matches):
        raw_name = match.group(1)
        # Keep only the text after the latest separator before the watt value.
        name = re.split(r"[,.;]|\band\b", raw_name, flags=re.IGNORECASE)[-1]
        name = _clean_appliance_name(name)
        if name:
            # Stop at the next watt value, leaving the current daily-usage phrase
            # available even when the next regex match begins in that phrase.
            next_start = (
                matches[index + 1].start(2) if index + 1 < len(matches) else len(message)
            )
            usage_text = message[match.end():next_start]
            hours_match = re.search(
                r"(?:daily\s+for\s+|for\s+)?(-?\d+(?:\.\d+)?)\s*"
                r"(hours?|hrs?|minutes?|mins?)\s*(?:per\s+day|/\s*day|daily)\b"
                r"|daily\s+for\s+(-?\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b",
                usage_text,
                re.IGNORECASE,
            )
            required_hours = None
            if hours_match:
                amount = float(hours_match.group(1) or hours_match.group(3))
                unit = (hours_match.group(2) or hours_match.group(4)).lower()
                required_hours = amount / 60 if unit.startswith("min") else amount
            appliances.append(
                {
                    "name": name,
                    "watts": float(match.group(2)),
                    "required_hours_per_day": required_hours,
                }
            )
    return appliances


def _fallback_extract(message: str) -> ApplianceExtraction:
    month, year = _extract_month_year(message)
    budget = _extract_budget(message)
    extracted_appliances = _extract_appliances(message)
    missing_hours = [
        item["name"]
        for item in extracted_appliances
        if item["required_hours_per_day"] is None
    ]
    if missing_hours:
        appliance_names = ", ".join(missing_hours)
        example_name = missing_hours[0]
        return ApplianceExtraction(
            year=year,
            month=month,
            max_budget_lkr=budget,
            error=(
                f"Please enter required hours per day for {appliance_names}. "
                f"Example: {example_name} 100W for 2 hours/day."
            ),
        )

    appliances = [ExtractedAppliance(**item) for item in extracted_appliances]
    return ApplianceExtraction(
        year=year,
        month=month,
        max_budget_lkr=budget,
        appliances=appliances,
    )


def _parse_tool_message_content(message: ToolMessage) -> Any | None:
    """Parse a tool result without trusting the agent's final response."""
    if getattr(message, "status", None) == "error":
        return None

    content = message.content
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    if isinstance(content, list) and len(content) == 1:
        block = content[0]
        if isinstance(block, dict):
            if isinstance(block.get("text"), str):
                try:
                    return json.loads(block["text"])
                except json.JSONDecodeError:
                    return None
            return block
    return None


def _tool_results(result: dict[str, Any], tool_name: str) -> list[Any | None]:
    return [
        _parse_tool_message_content(message)
        for message in result.get("messages", [])
        if isinstance(message, ToolMessage) and message.name == tool_name
    ]


def _find_single_tool_result(
    result: dict[str, Any], tool_name: str, action: str, result_label: str
) -> tuple[dict[str, Any] | None, str | None]:
    matches = _tool_results(result, tool_name)
    if not matches:
        return None, f"The appliance analyzer did not {action}. Please try again."
    if len(matches) != 1:
        return None, f"The appliance analyzer repeated {action}. Please try again."
    if not isinstance(matches[0], dict):
        return None, f"The appliance analyzer received an invalid {result_label} result."
    return matches[0], None


def _validation_error(validation: dict[str, Any]) -> str | None:
    if not isinstance(validation.get("is_valid"), bool):
        return "The appliance analyzer received an invalid validation result."
    errors = validation.get("errors")
    if not isinstance(errors, list) or not all(isinstance(item, str) for item in errors):
        return "The appliance analyzer received an invalid validation result."
    if validation["is_valid"]:
        return None
    if any("required hours per day must be provided" in item for item in errors):
        return (
            "Please include required hours per day for every appliance. "
            "Example: water motor 750W for 1.5 hours/day."
        )
    return "Please correct the following: " + ", ".join(errors) + "."


def _validated_input(
    validation: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    year = validation.get("year")
    month = validation.get("month")
    budget = validation.get("max_budget_lkr")
    appliances = validation.get("appliances")
    if (
        not isinstance(year, int)
        or isinstance(year, bool)
        or not isinstance(month, int)
        or isinstance(month, bool)
        or isinstance(budget, bool)
        or not isinstance(budget, (int, float))
        or not isinstance(appliances, list)
        or not appliances
        or not all(isinstance(item, dict) for item in appliances)
    ):
        return None, "The appliance analyzer received an invalid validation result."
    return {
        "year": year,
        "month": month,
        "max_budget_lkr": budget,
        "appliances": appliances,
    }, None


def _appliance_key(name: Any) -> str:
    return re.sub(r"\s+", " ", str(name).strip()).casefold()


def _collect_priority_results(
    result: dict[str, Any], appliances: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]] | None, str | None]:
    matches = _tool_results(result, classify_appliance_priority_tool.name)
    if any(not isinstance(item, dict) for item in matches):
        return None, "The appliance analyzer received an invalid priority result."

    priorities = [item for item in matches if isinstance(item, dict)]
    required_keys = {
        "item_name",
        "normalized_name",
        "priority",
        "category_note",
    }
    if any(
        not required_keys.issubset(item)
        or item["priority"] not in {"high", "medium", "low"}
        or not all(
            isinstance(item[key], str) and item[key].strip()
            for key in required_keys
        )
        for item in priorities
    ):
        return None, "The appliance analyzer received an invalid priority result."

    remaining = list(priorities)
    ordered = []
    for appliance in appliances:
        appliance_name = appliance.get("name")
        matching_indexes = [
            index
            for index, priority in enumerate(remaining)
            if _appliance_key(priority["item_name"]) == _appliance_key(appliance_name)
        ]
        if not matching_indexes:
            return (
                None,
                f"The appliance analyzer did not classify {appliance_name}. "
                "Please try again.",
            )
        if len(matching_indexes) > 1:
            return (
                None,
                f"The appliance analyzer classified {appliance_name} more than once.",
            )
        ordered.append(remaining.pop(matching_indexes[0]))

    if remaining:
        return None, "The appliance analyzer returned an unexpected priority result."
    return ordered, None


def _previous_plan_context(plan: dict[str, Any] | None) -> str | None:
    if not plan:
        return None
    appliance_parts = []
    for appliance in plan.get("appliances", []):
        appliance_parts.append(
            f"{appliance.get('name')} {appliance.get('watts')}W for "
            f"{appliance.get('required_hours_per_day')} hours/day"
        )
    return (
        "Previous successful plan, available only when the current request refers "
        f"to or modifies it: year {plan.get('year')}, month {plan.get('month')}, "
        f"maximum budget LKR {plan.get('max_budget_lkr')}, appliances: "
        + "; ".join(appliance_parts)
        + ". Current explicit values override these values."
    )


def _needs_previous_context(message: str) -> bool:
    lowered = message.lower()
    if re.search(
        r"\b(change|add|remove|replace|set|update|recalculate|my plan|my bill|it)\b",
        lowered,
    ):
        return True
    has_hours = bool(re.search(r"\b(?:hours?|hrs?|minutes?|mins?)\b", lowered))
    has_appliance_watts = bool(_extract_appliances(message))
    has_budget_only = bool(_extract_budget(message)) and not has_appliance_watts
    return (has_hours and not has_appliance_watts) or has_budget_only


def _appliance_agent_messages(state: HomeWattState) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if _needs_previous_context(state.get("message", "")):
        previous_context = _previous_plan_context(state.get("previous_plan"))
        if previous_context:
            messages.append({"role": "system", "content": previous_context})
        messages.extend(dict(item) for item in state.get("conversation_history", []))
    messages.append({"role": "user", "content": state.get("message", "")})
    return messages


async def appliance_analyzer_node(state: HomeWattState) -> HomeWattState:
    """Extract year, month, budget, and appliances from the user message."""
    message = state.get("message", "")
    if _is_greeting(message):
        return {
            **state,
            "intent": "greeting",
            "casual_response": "Hi, how can I assist you today?",
        }

    fallback_extraction = _fallback_extract(message)
    if fallback_extraction.error:
        return {
            **state,
            "error": fallback_extraction.error,
        }

    if not has_openai_config():
        return {
            **state,
            "error": "The appliance analyzer is unavailable. Please try again later.",
        }

    try:
        agent = create_appliance_analyzer_agent()
        result = await agent.ainvoke(
            {"messages": _appliance_agent_messages(state)}
        )
    except Exception:
        return {
            **state,
            "error": "Could not complete appliance analysis. Please try again.",
        }

    validation, error = _find_single_tool_result(
        result,
        validate_appliance_input_tool.name,
        "validate the appliance details",
        "appliance validation",
    )
    if error:
        return {**state, "error": error}

    error = _validation_error(validation)
    if error:
        return {**state, "error": error}

    validated, error = _validated_input(validation)
    if error:
        return {**state, "error": error}

    appliance_priorities, error = _collect_priority_results(
        result, validated["appliances"]
    )
    if error:
        return {**state, "error": error}

    return {
        **state,
        "year": validated["year"],
        "month": validated["month"],
        "max_budget_lkr": validated["max_budget_lkr"],
        "appliances": validated["appliances"],
        "appliance_priorities": appliance_priorities,
    }
