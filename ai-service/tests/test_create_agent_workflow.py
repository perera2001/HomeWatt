"""Tests for the create_agent workflow and controlled fallback behavior."""

import unittest

from app.agents.guide_agent import create_guide_writer_agent
from app.agents.supervisor import create_supervisor_agent
from app.config import settings
from app.graph.workflow import run_homewatt_workflow
from app.memory.session_memory import clear_session_memory


class CreateAgentWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_openai_api_key = settings.openai_api_key
        settings.openai_api_key = ""

    def tearDown(self):
        settings.openai_api_key = self.original_openai_api_key

    async def asyncSetUp(self):
        await clear_session_memory(1, 1)

    def test_create_agent_factories_exist(self):
        self.assertTrue(callable(create_supervisor_agent))
        self.assertTrue(callable(create_guide_writer_agent))

    async def test_workflow_uses_mcp_results_for_planning(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message="calculate this structured plan",
            year=2026,
            month=5,
            max_budget_lkr=3000,
            appliances=[
                {
                    "name": "TV",
                    "watts": 100,
                    "required_hours_per_day": 2,
                    "priority": "low",
                },
                {
                    "name": "iron",
                    "watts": 1000,
                    "required_hours_per_day": 0.25,
                    "priority": "medium",
                },
                {
                    "name": "water motor",
                    "watts": 750,
                    "required_hours_per_day": 1.5,
                    "priority": "high",
                },
            ],
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
        self.assertNotIn("priority_rules_resource", state)


if __name__ == "__main__":
    unittest.main()
