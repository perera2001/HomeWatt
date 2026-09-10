"""Prompt templates grounded only in deterministic MCP tool results."""


def create_usage_guide_prompt(
    year: int,
    month: int,
    max_budget_lkr: float,
    appliances: str,
    usage_plan: str,
    bill_breakdown: str,
) -> str:
    """Build instructions for a simple Sri Lankan household usage guide."""
    return f"""Create a simple Sri Lankan home electricity usage guide.

Planning period: {year}-{month:02d}
Maximum monthly budget: LKR {max_budget_lkr}
Appliances supplied by the user: {appliances}
Usage plan tool result: {usage_plan}
Bill breakdown tool result: {bill_breakdown}

Mention every appliance, its watts, suggested hours per day, and monthly units.
Explain clearly whether the plan stays under budget and state the final estimated bill.
Do not invent tariff values or perform a different tariff calculation.
Use only the supplied tool results for all calculated values."""


def explain_bill_breakdown_prompt(bill_breakdown: str) -> str:
    """Build instructions for a plain-language bill explanation."""
    return f"""Explain this Sri Lankan domestic electricity bill calculation simply:

{bill_breakdown}

Include the billing days, adjusted unit limits, tariff case, energy charge,
fixed charge, SSC levy, and final bill. Do not recalculate or change any value
from the tool result."""
