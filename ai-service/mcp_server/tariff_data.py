"""Deterministic Sri Lankan domestic electricity tariff calculations."""

import calendar
import math
from typing import Any


TARIFF_DATA: dict[str, Any] = {
    "country": "Sri Lanka",
    "consumer_category": "Domestic",
    "tariff_version": "2026-05",
    "effective_from": "2026-05-11",
    "billing_period_rule": (
        "Standard unit blocks are based on 30 days and must be adjusted "
        "using the number of billing days."
    ),
    "voltage": "230V",
    "frequency": "50Hz",
    "tariff_calculation_method": {
        "case_1": "U <= D: energy = U * 5; fixed charge = 80",
        "case_2": "D < U <= 2D: energy = (D * 5) + ((U - D) * 9); fixed charge = 210",
        "case_3": "2D < U <= 3D: energy = (2D * 14) + ((U - 2D) * 20); fixed charge = 400",
        "case_4": "3D < U <= 4D: energy = (2D * 14) + (D * 20) + ((U - 3D) * 28); fixed charge = 1000",
        "case_5": "4D < U <= 6D: energy = (2D * 14) + (D * 20) + (D * 28) + ((U - 4D) * 44); fixed charge = 1500",
        "case_6": "U > 6D: energy = (6D * 32.50) + ((U - 6D) * 100); fixed charge = 2500",
    },
    "ssc_levy_formula": "base_charge * 2.5 / 97.5",
    "monthly_bill_formula": "base_charge + ssc_levy",
    "source_note": "PUCSL/CEB approved domestic tariff effective from 11 May 2026",
}


def _positive_year(year: int) -> int:
    if isinstance(year, bool) or not isinstance(year, int) or year < 1:
        raise ValueError("year must be a positive integer")
    return year


def _finite_number(value: float, name: str, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")

    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return number


def get_billing_days_data(year: int, month: int) -> dict[str, int]:
    """Return calendar billing days, including leap-year handling."""
    valid_year = _positive_year(year)
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("month must be an integer from 1 to 12")

    return {
        "year": valid_year,
        "month": month,
        "billing_days": calendar.monthrange(valid_year, month)[1],
    }


def calculate_appliance_kwh_data(
    watts: float, hours_per_day: float, days: int
) -> dict[str, float | int]:
    """Calculate monthly appliance energy from watts and daily usage."""
    valid_watts = _finite_number(watts, "watts", minimum=0.000001)
    valid_hours = _finite_number(hours_per_day, "hours_per_day")
    if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
        raise ValueError("days must be a positive integer")

    return {
        "watts": valid_watts,
        "hours_per_day": valid_hours,
        "days": days,
        "kwh": round(valid_watts * valid_hours * days / 1000, 4),
    }


def calculate_domestic_bill_data(
    year: int,
    month: int,
    units: float,
    credit_balance: float = 0,
    debit_balance: float = 0,
) -> dict[str, Any]:
    """Calculate a domestic bill using the tariff effective 11 May 2026."""
    billing = get_billing_days_data(year, month)
    billing_days = billing["billing_days"]
    valid_units = _finite_number(units, "units")
    valid_credit = _finite_number(credit_balance, "credit_balance")
    valid_debit = _finite_number(debit_balance, "debit_balance")
    day_block = float(billing_days)

    if valid_units <= day_block:
        tariff_case = "case_1"
        energy_charge = valid_units * 5
        fixed_charge = 80
    elif valid_units <= 2 * day_block:
        tariff_case = "case_2"
        energy_charge = (day_block * 5) + ((valid_units - day_block) * 9)
        fixed_charge = 210
    elif valid_units <= 3 * day_block:
        tariff_case = "case_3"
        energy_charge = (2 * day_block * 14) + ((valid_units - 2 * day_block) * 20)
        fixed_charge = 400
    elif valid_units <= 4 * day_block:
        tariff_case = "case_4"
        energy_charge = (
            (2 * day_block * 14)
            + (day_block * 20)
            + ((valid_units - 3 * day_block) * 28)
        )
        fixed_charge = 1000
    elif valid_units <= 6 * day_block:
        tariff_case = "case_5"
        energy_charge = (
            (2 * day_block * 14)
            + (day_block * 20)
            + (day_block * 28)
            + ((valid_units - 4 * day_block) * 44)
        )
        fixed_charge = 1500
    else:
        tariff_case = "case_6"
        energy_charge = (6 * day_block * 32.50) + ((valid_units - 6 * day_block) * 100)
        fixed_charge = 2500

    base_charge = energy_charge + fixed_charge
    ssc_levy = base_charge * 2.5 / 97.5
    monthly_bill = base_charge + ssc_levy
    final_amount_due = monthly_bill - valid_credit + valid_debit

    return {
        "year": year,
        "month": month,
        "units": round(valid_units, 4),
        "billing_days": billing_days,
        "adjusted_limits": {
            "30_unit_limit": billing_days,
            "60_unit_limit": 2 * billing_days,
            "90_unit_limit": 3 * billing_days,
            "120_unit_limit": 4 * billing_days,
            "180_unit_limit": 6 * billing_days,
        },
        "tariff_case": tariff_case,
        "energy_charge": round(energy_charge, 2),
        "fixed_charge": round(fixed_charge, 2),
        "base_charge": round(base_charge, 2),
        "ssc_levy": round(ssc_levy, 2),
        "monthly_bill": round(monthly_bill, 2),
        "credit_balance": round(valid_credit, 2),
        "debit_balance": round(valid_debit, 2),
        "final_amount_due": round(final_amount_due, 2),
    }


def calculate_budget_unit_limit_data(
    year: int, month: int, max_budget_lkr: float
) -> dict[str, float | int]:
    """Estimate the largest two-decimal unit value that fits the budget."""
    budget = _finite_number(max_budget_lkr, "max_budget_lkr")
    billing_days = get_billing_days_data(year, month)["billing_days"]
    zero_unit_bill = calculate_domestic_bill_data(year, month, 0)["monthly_bill"]

    if budget < zero_unit_bill:
        return {
            "max_budget_lkr": round(budget, 2),
            "estimated_allowed_units": 0.0,
            "estimated_bill": zero_unit_bill,
            "billing_days": billing_days,
        }

    low = 0.0
    high = float(6 * billing_days)
    while calculate_domestic_bill_data(year, month, high)["monthly_bill"] <= budget:
        low = high
        high *= 2

    for _ in range(80):
        midpoint = (low + high) / 2
        if calculate_domestic_bill_data(year, month, midpoint)["monthly_bill"] <= budget:
            low = midpoint
        else:
            high = midpoint

    allowed_units = math.floor((low + 1e-9) * 100) / 100
    estimated_bill = calculate_domestic_bill_data(year, month, allowed_units)["monthly_bill"]

    return {
        "max_budget_lkr": round(budget, 2),
        "estimated_allowed_units": allowed_units,
        "estimated_bill": estimated_bill,
        "billing_days": billing_days,
    }
