"""Tests for the stdio MCP client helpers."""

import unittest

from app.mcp_client.client import (
    calculate_domestic_bill_via_mcp,
    generate_initial_usage_plan_via_mcp,
    read_appliance_priority_rules_via_mcp,
    read_tariff_resource_via_mcp,
)


class MCPClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_calculate_domestic_bill_via_mcp(self):
        result = await calculate_domestic_bill_via_mcp(2026, 5, 105)

        self.assertEqual(result["billing_days"], 31)
        self.assertAlmostEqual(result["final_amount_due"], 2896.41, places=2)

    async def test_generate_initial_usage_plan_via_mcp(self):
        result = await generate_initial_usage_plan_via_mcp(
            2026,
            5,
            3000,
            [
                {"name": "TV", "watts": 100, "required_hours_per_day": 2},
                {"name": "Iron", "watts": 1000, "required_hours_per_day": 0.25},
                {"name": "Water motor", "watts": 750, "required_hours_per_day": 1.5},
            ],
        )

        self.assertEqual(result["year"], 2026)
        self.assertEqual(result["month"], 5)
        self.assertEqual(result["billing_days"], 31)
        self.assertLessEqual(result["estimated_bill"], 3000)
        self.assertEqual(len(result["appliances"]), 3)
        self.assertEqual(result["appliances"][0]["required_hours_per_day"], 2)

    async def test_resources_remain_explicitly_readable(self):
        tariff = await read_tariff_resource_via_mcp()
        priorities = await read_appliance_priority_rules_via_mcp()

        self.assertEqual(tariff["tariff_version"], "2026-05")
        self.assertIn("TV", priorities)


if __name__ == "__main__":
    unittest.main()
