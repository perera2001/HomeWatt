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

The usage-plan result contains the requested usage, required hours, requested
total units, minimum required budget, minimum possible zero-unit bill, budget
shortfall or remaining budget, feasibility and requirement status, and an
affordable adjusted plan when one exists.

Never change calculated numbers or perform a tariff calculation. Never claim
the user's requirements were satisfied when appliance hours were reduced.
Clearly distinguish requested hours from suggested affordable hours. If the
budget is below the zero-unit bill, clearly state that no plan can fit it.
Do not invent appliances, watts, hours, or tariff values. End a successful plan
with one or two practical sentences about reducing the bill, reducing
low-priority usage before essential high-priority usage."""


def explain_bill_breakdown_prompt(bill_breakdown: str) -> str:
    """Build instructions for a plain-language bill explanation."""
    return f"""Explain this Sri Lankan domestic electricity bill calculation simply:

{bill_breakdown}

Include the billing days, adjusted unit limits, tariff case, energy charge,
fixed charge, SSC levy, and final bill. Do not recalculate or change any value
from the tool result."""
