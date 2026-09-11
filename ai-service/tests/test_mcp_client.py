"""Tests for the stdio MCP client helpers."""

import unittest

from app.mcp_client.client import (
    calculate_domestic_bill_via_mcp,
    generate_initial_usage_plan_via_mcp,
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
                {"name": "TV", "watts": 100},
                {"name": "Iron", "watts": 1000},
                {"name": "Water motor", "watts": 750},
            ],
        )

        self.assertEqual(result["year"], 2026)
        self.assertEqual(result["month"], 5)
        self.assertEqual(result["billing_days"], 31)
        self.assertLessEqual(result["estimated_bill"], 3000)
        self.assertEqual(len(result["appliances"]), 3)


if __name__ == "__main__":
    unittest.main()
