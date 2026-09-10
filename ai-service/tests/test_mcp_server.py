"""Tests for deterministic MCP tariff and appliance behavior."""

import unittest

from mcp_server.appliance_rules import (
    classify_appliance_priority_data,
    generate_initial_usage_plan_data,
)
from mcp_server.tariff_data import (
    calculate_appliance_kwh_data,
    calculate_budget_unit_limit_data,
    calculate_domestic_bill_data,
    get_billing_days_data,
)


class TariffToolTests(unittest.TestCase):
    def test_billing_days_handles_leap_year(self):
        self.assertEqual(get_billing_days_data(2024, 2)["billing_days"], 29)
        self.assertEqual(get_billing_days_data(2026, 2)["billing_days"], 28)

    def test_appliance_kwh(self):
        result = calculate_appliance_kwh_data(100, 2, 31)
        self.assertEqual(result["kwh"], 6.2)

    def test_may_2026_bill_example(self):
        result = calculate_domestic_bill_data(2026, 5, 105)
        self.assertEqual(result["billing_days"], 31)
        self.assertEqual(result["tariff_case"], "case_4")
        self.assertEqual(result["energy_charge"], 1824.00)
        self.assertEqual(result["fixed_charge"], 1000.00)
        self.assertEqual(result["final_amount_due"], 2896.41)

    def test_tariff_case_boundaries(self):
        cases = (
            (31, "case_1"),
            (31.01, "case_2"),
            (62, "case_2"),
            (62.01, "case_3"),
            (93, "case_3"),
            (93.01, "case_4"),
            (124, "case_4"),
            (124.01, "case_5"),
            (186, "case_5"),
            (186.01, "case_6"),
        )

        for units, expected_case in cases:
            with self.subTest(units=units):
                result = calculate_domestic_bill_data(2026, 5, units)
                self.assertEqual(result["tariff_case"], expected_case)

    def test_budget_limit_stays_under_budget(self):
        result = calculate_budget_unit_limit_data(2026, 5, 3000)
        self.assertLessEqual(result["estimated_bill"], 3000)


class ApplianceToolTests(unittest.TestCase):
    def test_decorative_lights_are_low_priority(self):
        result = classify_appliance_priority_data("Decorative lights")
        self.assertEqual(result["priority"], "low")

    def test_smart_tv_is_low_priority(self):
        result = classify_appliance_priority_data("Smart TV")
        self.assertEqual(result["priority"], "low")

    def test_unknown_appliance_defaults_to_medium(self):
        result = classify_appliance_priority_data("Desktop computer")
        self.assertEqual(result["priority"], "medium")

    def test_usage_plan_respects_normal_budget(self):
        result = generate_initial_usage_plan_data(
            2026,
            5,
            3000,
            [
                {"name": "TV", "watts": 100},
                {"name": "Iron", "watts": 1000},
                {"name": "Water motor", "watts": 750},
            ],
        )
        self.assertTrue(result["stays_within_budget"])
        self.assertLessEqual(result["estimated_bill"], 3000)


if __name__ == "__main__":
    unittest.main()
