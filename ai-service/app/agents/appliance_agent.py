"""Rule-based appliance analyzer agent."""

import re
from typing import Any

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
        r"^(?:and|with|i\s+have|we\s+have|have|has|a|an|the)\s+",
        "",
        name.strip(),
        flags=re.I,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" .,-:")


def _extract_appliances(message: str) -> list[dict[str, Any]]:
    appliance_pattern = re.compile(
        r"([a-zA-Z][a-zA-Z ]*?)\s+(\d+(?:\.\d+)?)\s*(?:w|watts)\b",
        re.IGNORECASE,
    )
    appliances = []
    for match in appliance_pattern.finditer(message):
        raw_name = match.group(1)
        # Keep only the text after the latest separator before the watt value.
        name = re.split(r"[,.;]|\band\b", raw_name, flags=re.IGNORECASE)[-1]
        name = _clean_appliance_name(name)
        if name:
            appliances.append({"name": name, "watts": float(match.group(2))})
    return appliances


async def appliance_analyzer_node(state: HomeWattState) -> HomeWattState:
    """Extract year, month, budget, and appliances from a simple user message."""
    message = state.get("message", "")
    if _is_greeting(message):
        return {
            **state,
            "intent": "greeting",
            "casual_response": "Hi, how can I assist you today?",
        }

    month, year = _extract_month_year(message)
    budget = _extract_budget(message)
    appliances = _extract_appliances(message)

    missing = []
    if year is None or month is None:
        missing.append("month and year")
    if budget is None:
        missing.append("budget")
    if not appliances:
        missing.append("appliances with watt values")

    if missing:
        return {
            **state,
            "error": "Please include " + ", ".join(missing) + ".",
        }

    return {
        **state,
        "year": year,
        "month": month,
        "max_budget_lkr": budget,
        "appliances": appliances,
    }
