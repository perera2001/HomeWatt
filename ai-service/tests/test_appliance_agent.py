"""Focused tests for structured appliance input."""

import unittest

from app.agents.appliance_agent import (
    STRUCTURED_PLAN_REQUIRED_MESSAGE,
    appliance_analyzer_node,
)


ONE_APPLIANCE = [
    {
        "name": "TV",
        "watts": 100.0,
        "required_hours_per_day": 2.0,
        "priority": "low",
    },
]
THREE_APPLIANCES = [
    *ONE_APPLIANCE,
    {
        "name": "iron",
        "watts": 1000.0,
        "required_hours_per_day": 0.25,
        "priority": "medium",
    },
    {
        "name": "water motor",
        "watts": 750.0,
        "required_hours_per_day": 1.5,
        "priority": "high",
    },
]


class ApplianceAnalyzerNodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_input_uses_supplied_appliances_and_priorities(self):
        state = await appliance_analyzer_node(
            {
                "message": "calculate this structured plan",
                "structured_input": True,
                "structured_year": 2026,
                "structured_month": 9,
                "structured_max_budget_lkr": 1000.0,
                "structured_appliances": THREE_APPLIANCES,
            }
        )

        self.assertEqual(state["year"], 2026)
        self.assertEqual(state["month"], 9)
        self.assertEqual(state["max_budget_lkr"], 1000.0)
        self.assertEqual(state["appliances"], THREE_APPLIANCES)
        self.assertEqual(
            [item["priority"] for item in state["appliance_priorities"]],
            ["low", "medium", "high"],
        )
        self.assertEqual(state["appliance_priorities"][0]["item_name"], "TV")

    async def test_free_text_planning_is_rejected_by_appliance_node(self):
        state = await appliance_analyzer_node(
            {
                "message": "My budget is Rs. 600 for May 2026. TV 100W for 2 hours/day.",
            }
        )

        self.assertEqual(state["error"], STRUCTURED_PLAN_REQUIRED_MESSAGE)
        self.assertNotIn("appliances", state)


if __name__ == "__main__":
    unittest.main()
