"""Tests for the rule-based HomeWatt LangGraph workflow."""

import unittest

from app.config import settings
from app.graph.workflow import run_homewatt_workflow


class HomeWattWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_openai_api_key = settings.openai_api_key
        settings.openai_api_key = ""

    def tearDown(self):
        settings.openai_api_key = self.original_openai_api_key

    async def test_greeting_returns_casual_response(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message="hello",
        )

        self.assertEqual(result["answer"], "Hi, how can I assist you today?")
        self.assertEqual(result["state"]["intent"], "greeting")
        self.assertNotIn("error", result["state"])
        self.assertNotIn("usage_plan", result["state"])

    async def test_budget_message_creates_usage_plan(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message=(
                "My budget is Rs. 3000 for May 2026. "
                "I have TV 100W, iron 1000W and water motor 750W."
            ),
        )

        answer = result["answer"]
        state = result["state"]

        self.assertIn("HomeWatt Advisor usage plan", answer)
        self.assertIn("TV", answer)
        self.assertIn("iron", answer)
        self.assertIn("water motor", answer)
        self.assertIn("Rs. 3,000.00", answer)
        self.assertIn("Estimated bill", answer)

        self.assertEqual(state["year"], 2026)
        self.assertEqual(state["month"], 5)
        self.assertEqual(state["max_budget_lkr"], 3000)
        self.assertEqual(len(state["appliances"]), 3)
        self.assertEqual(state["usage_plan"]["year"], 2026)
        self.assertIn("estimated_bill", state["usage_plan"])


if __name__ == "__main__":
    unittest.main()
