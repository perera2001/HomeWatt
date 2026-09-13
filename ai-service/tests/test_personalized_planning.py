"""Tests for household-required hours and affordable planning."""

import unittest
from unittest.mock import AsyncMock, patch

from app.agents.bill_agent import bill_calculator_node
from app.agents.guide_agent import _format_plan_answer
from app.agents.optimizer_agent import usage_optimizer_node
from app.mcp_client.client import MCPClientError
from mcp_server.appliance_rules import generate_initial_usage_plan_data
from mcp_server.tariff_data import calculate_domestic_bill_data


APPLIANCES = [
    {"name": "TV", "watts": 100, "required_hours_per_day": 2},
    {"name": "Iron", "watts": 1000, "required_hours_per_day": 0.25},
    {"name": "Water motor", "watts": 750, "required_hours_per_day": 1.5},
]


class PersonalizedPlanTests(unittest.TestCase):
    def test_requested_plan_fits_budget_exactly_as_supplied(self):
        result = generate_initial_usage_plan_data(2026, 5, 600, APPLIANCES)
        self.assertEqual(result["requested_total_units"], 48.83)
        self.assertEqual(result["minimum_required_budget"], 538.94)
        self.assertEqual(result["remaining_budget"], 61.06)
        self.assertTrue(result["requirements_met"])
        self.assertFalse(result["adjustments_required"])
        self.assertTrue(result["budget_feasible"])
        self.assertEqual(
            [item["suggested_hours_per_day"] for item in result["appliances"]],
            [2, 0.25, 1.5],
        )

    def test_over_budget_plan_reduces_by_priority(self):
        result = generate_initial_usage_plan_data(2026, 5, 400, APPLIANCES)
        tv, iron, motor = result["appliances"]
        self.assertEqual(result["minimum_required_budget"], 538.94)
        self.assertEqual(result["budget_shortfall"], 138.94)
        self.assertFalse(result["requirements_met"])
        self.assertTrue(result["adjustments_required"])
        self.assertEqual(tv["suggested_hours_per_day"], 0)
        self.assertEqual(iron["suggested_hours_per_day"], 0)
        self.assertLess(motor["suggested_hours_per_day"], 1.5)
        self.assertLessEqual(result["estimated_bill"], 400)

    def test_budget_below_zero_unit_bill_has_no_plan(self):
        result = generate_initial_usage_plan_data(2026, 5, 10, APPLIANCES)
        self.assertEqual(result["minimum_possible_bill"], 82.05)
        self.assertEqual(result["minimum_required_budget"], 538.94)
        self.assertEqual(result["budget_shortfall"], 528.94)
        self.assertFalse(result["budget_feasible"])
        self.assertFalse(result["stays_within_budget"])
        self.assertIsNone(result["affordable_plan"])

    def _three_equal_priority_plan(self, target_units):
        appliances = [
            {"name": "TV", "watts": 1000, "required_hours_per_day": 1},
            {"name": "Iron", "watts": 1000, "required_hours_per_day": 1},
            {"name": "Water motor", "watts": 1000, "required_hours_per_day": 1},
        ]
        budget = calculate_domestic_bill_data(2026, 5, target_units)["monthly_bill"]
        return generate_initial_usage_plan_data(2026, 5, budget, appliances)

    def test_low_priority_is_reduced_before_medium(self):
        result = self._three_equal_priority_plan(80)
        tv, iron, motor = result["appliances"]
        self.assertLess(tv["suggested_hours_per_day"], 1)
        self.assertEqual(iron["suggested_hours_per_day"], 1)
        self.assertEqual(motor["suggested_hours_per_day"], 1)

    def test_medium_is_reduced_before_high(self):
        result = self._three_equal_priority_plan(50)
        tv, iron, motor = result["appliances"]
        self.assertEqual(tv["suggested_hours_per_day"], 0)
        self.assertLess(iron["suggested_hours_per_day"], 1)
        self.assertEqual(motor["suggested_hours_per_day"], 1)

    def test_high_priority_is_reduced_only_when_needed(self):
        result = self._three_equal_priority_plan(20)
        tv, iron, motor = result["appliances"]
        self.assertEqual(tv["suggested_hours_per_day"], 0)
        self.assertEqual(iron["suggested_hours_per_day"], 0)
        self.assertLess(motor["suggested_hours_per_day"], 1)

    def test_same_priority_group_is_reduced_proportionally(self):
        appliances = [
            {"name": "TV", "watts": 100, "required_hours_per_day": 4},
            {"name": "Decorative lights", "watts": 200, "required_hours_per_day": 4},
        ]
        budget = calculate_domestic_bill_data(2026, 5, 20)["monthly_bill"]
        result = generate_initial_usage_plan_data(2026, 5, budget, appliances)
        first, second = result["appliances"]
        self.assertAlmostEqual(
            first["suggested_hours_per_day"], second["suggested_hours_per_day"], places=4
        )

    def test_tariff_boundary_rounding_never_exceeds_budget(self):
        budget = calculate_domestic_bill_data(2026, 5, 31)["monthly_bill"]
        result = generate_initial_usage_plan_data(
            2026,
            5,
            budget,
            [{"name": "TV", "watts": 1000, "required_hours_per_day": 1.1}],
        )
        self.assertLessEqual(result["estimated_bill"], budget)
        self.assertTrue(result["stays_within_budget"])

    def test_required_hours_are_rejected_by_server(self):
        for hours in (None, 0, -1, 25):
            appliance = {"name": "TV", "watts": 100}
            if hours is not None:
                appliance["required_hours_per_day"] = hours
            with self.subTest(hours=hours), self.assertRaises(ValueError):
                generate_initial_usage_plan_data(2026, 5, 600, [appliance])


class MCPNodeErrorTests(unittest.IsolatedAsyncioTestCase):
    @patch(
        "app.agents.bill_agent.calculate_budget_unit_limit_via_mcp",
        new_callable=AsyncMock,
        return_value={},
    )
    async def test_invalid_bill_response_is_readable(self, _mock_call):
        state = await bill_calculator_node(
            {"year": 2026, "month": 5, "max_budget_lkr": 600}
        )
        self.assertIn("invalid MCP response", state["error"])

    @patch(
        "app.agents.optimizer_agent.generate_initial_usage_plan_via_mcp",
        new_callable=AsyncMock,
        side_effect=MCPClientError("tool failed"),
    )
    async def test_usage_plan_mcp_error_is_readable(self, _mock_call):
        state = await usage_optimizer_node(
            {
                "year": 2026,
                "month": 5,
                "max_budget_lkr": 600,
                "appliances": APPLIANCES,
            }
        )
        self.assertIn("Could not generate usage plan", state["error"])


class DeterministicGuideTests(unittest.TestCase):
    def _state(self, budget):
        plan = generate_initial_usage_plan_data(2026, 5, budget, APPLIANCES)
        return {**plan, "usage_plan": plan}

    def test_exact_plan_answer_reports_requirements(self):
        answer = _format_plan_answer(self._state(600))
        self.assertIn("Remaining budget: Rs. 61.06", answer)
        self.assertIn("2 required hours/day", answer)
        self.assertIn("All requested usage requirements are satisfied", answer)

    def test_adjusted_answer_distinguishes_hours(self):
        answer = _format_plan_answer(self._state(400))
        self.assertIn("Requested hours -> suggested affordable hours", answer)
        self.assertIn("not all original requirements are satisfied", answer)
        self.assertIn("Adjusted estimated bill: Rs. 399.84", answer)

    def test_impossible_answer_explains_fixed_cost(self):
        answer = _format_plan_answer(self._state(10))
        self.assertIn("Minimum possible bill, even at zero units: Rs. 82.05", answer)
        self.assertIn("No electricity usage plan can remain within Rs. 10.00", answer)


if __name__ == "__main__":
    unittest.main()
