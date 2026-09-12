"""Appliance analyzer agent."""

import json
import re
from typing import Any

from langchain.agents import create_agent
from pydantic import BaseModel, Field

from app.agents.llm import create_chat_model, has_openai_config
from app.agents.tools import (
    classify_appliance_priority_tool,
    validate_appliance_input_tool,
)
from app.graph.state import HomeWattState
from app.mcp_client.client import MCPClientError


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
    "Required hours must be greater than 0 and no more than 24. If information "
    "is missing, return a clear error. Use tools to validate input and classify "
    "appliance priorities."
)


def create_appliance_analyzer_agent():
    """Create the LLM-powered appliance analyzer agent."""
    return create_agent(
        model=create_chat_model(),
        tools=[validate_appliance_input_tool, classify_appliance_priority_tool],
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


def _extraction_from_agent_result(result: dict) -> ApplianceExtraction:
    structured = result.get("structured_response")
    if isinstance(structured, ApplianceExtraction):
        return structured
    if isinstance(structured, dict):
        try:
            return ApplianceExtraction(**structured)
        except ValueError:
            return ApplianceExtraction(
                error="Please include required hours per day for every appliance."
            )

    content = result.get("messages", [])[-1].content if result.get("messages") else "{}"
    try:
        return ApplianceExtraction(**json.loads(content))
    except (json.JSONDecodeError, TypeError, ValueError):
        return ApplianceExtraction(error="Could not extract the planning details.")


def _missing_fields_error(extraction: ApplianceExtraction) -> str | None:
    if extraction.error:
        return extraction.error

    appliances = [item.model_dump() for item in extraction.appliances]
    validation = validate_appliance_input_tool.invoke(
        {
            "year": extraction.year or 0,
            "month": extraction.month or 0,
            "max_budget_lkr": extraction.max_budget_lkr or 0,
            "appliances_json": json.dumps(appliances),
        }
    )
    if validation["is_valid"]:
        return None
    if any(
        "required hours per day must be provided" in item
        for item in validation["errors"]
    ):
        return (
            "Please include required hours per day for every appliance. "
            "Example: water motor 750W for 1.5 hours/day."
        )
    return "Please correct the following: " + ", ".join(validation["errors"]) + "."


async def _classify_appliances(appliances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priorities = []
    for appliance in appliances:
        priorities.append(
            await classify_appliance_priority_tool.ainvoke(
                {"item_name": appliance["name"]}
            )
        )
    return priorities


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

    used_openai = has_openai_config()
    if used_openai:
        try:
            agent = create_appliance_analyzer_agent()
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
            extraction = _extraction_from_agent_result(result)
        except Exception:
            extraction = fallback_extraction
    else:
        extraction = fallback_extraction

    error = _missing_fields_error(extraction)
    if error and used_openai:
        fallback_error = _missing_fields_error(fallback_extraction)
        if not fallback_error:
            extraction = fallback_extraction
            error = None

    if error:
        return {
            **state,
            "error": error,
        }

    appliances = [item.model_dump() for item in extraction.appliances]
    try:
        appliance_priorities = await _classify_appliances(appliances)
    except MCPClientError as exc:
        return {
            **state,
            "error": f"Could not classify appliance priorities: {exc}",
        }

    return {
        **state,
        "year": extraction.year,
        "month": extraction.month,
        "max_budget_lkr": extraction.max_budget_lkr,
        "appliances": appliances,
        "appliance_priorities": appliance_priorities,
    }
