"""Tests for the hybrid create_agent workflow with deterministic fallback."""

import unittest

from app.agents.appliance_agent import create_appliance_analyzer_agent
from app.agents.guide_agent import create_guide_writer_agent
from app.agents.supervisor import create_supervisor_agent
from app.config import settings
from app.graph.workflow import run_homewatt_workflow


class CreateAgentWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_openai_api_key = settings.openai_api_key
        settings.openai_api_key = ""

    def tearDown(self):
        settings.openai_api_key = self.original_openai_api_key

    def test_create_agent_factories_exist(self):
        self.assertTrue(callable(create_supervisor_agent))
        self.assertTrue(callable(create_appliance_analyzer_agent))
        self.assertTrue(callable(create_guide_writer_agent))

    async def test_workflow_uses_mcp_results_for_planning(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message=(
                "My budget is Rs. 3000 for May 2026. "
                "I need TV 100W for 2 hours/day, iron 1000W for 0.25 hours/day "
                "and water motor 750W for 1.5 hours/day."
            ),
        )

        answer = result["answer"]
        state = result["state"]

        self.assertIn("Requested usage", answer)
        self.assertIn("Estimated bill", answer)
        self.assertEqual(state["year"], 2026)
        self.assertEqual(state["month"], 5)
        self.assertEqual(state["max_budget_lkr"], 3000)
        self.assertEqual(
            [item["name"] for item in state["appliances"]],
            ["TV", "iron", "water motor"],
        )
        self.assertEqual(state["estimated_bill"], state["usage_plan"]["estimated_bill"])
        self.assertIn("budget_limit_result", state)
        self.assertNotIn("tariff_resource", state)
        self.assertNotIn("appliance_rules_resource", state)


if __name__ == "__main__":
    unittest.main()
