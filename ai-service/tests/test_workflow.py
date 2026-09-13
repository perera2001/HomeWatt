"""Tests for the HomeWatt LangGraph workflow."""

import unittest
from unittest.mock import patch

from app.config import settings
from app.graph.workflow import run_homewatt_workflow
from app.memory.session_memory import clear_session_memory


class HomeWattWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_openai_api_key = settings.openai_api_key
        settings.openai_api_key = ""

    def tearDown(self):
        settings.openai_api_key = self.original_openai_api_key

    async def asyncSetUp(self):
        await clear_session_memory(1, 1)

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

    async def test_free_text_budget_message_requires_form(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message=(
                "My budget is Rs. 3000 for May 2026. "
                "I need TV 100W for 2 hours/day, iron 1000W for 15 minutes/day "
                "and water motor 750W for 1.5 hours/day."
            ),
        )

        self.assertEqual(result["state"]["intent"], "form_required")
        self.assertIn("add your appliances in the table first", result["answer"])
        self.assertNotIn("usage_plan", result["state"])

    async def test_structured_input_creates_usage_plan_without_appliance_agent(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message="calculate this structured plan",
            year=2026,
            month=5,
            max_budget_lkr=600,
            appliances=[
                {
                    "name": "Desktop computer",
                    "watts": 1000,
                    "required_hours_per_day": 1,
                    "priority": "low",
                }
            ],
        )

        state = result["state"]
        self.assertEqual(state["intent"], "usage_plan")
        self.assertEqual(state["appliances"][0]["name"], "Desktop computer")
        self.assertEqual(state["appliances"][0]["priority"], "low")
        self.assertEqual(
            state["requested_plan"]["appliances"][0]["priority"],
            "low",
        )
        self.assertIn("HomeWatt Advisor usage plan", result["answer"])
        self.assertIn("requested_plan", result["plan_snapshot"])

    async def test_followup_can_use_previous_plan_from_backend(self):
        previous_plan = {
            "estimated_bill": 528.46,
            "requested_plan": {
                "appliances": [
                    {
                        "name": "table lamp",
                        "watts": 100,
                        "normalized_name": "table lamp",
                        "priority": "low",
                        "required_hours_per_day": 2,
                    },
                    {
                        "name": "water motor",
                        "watts": 750,
                        "normalized_name": "water motor",
                        "priority": "high",
                        "required_hours_per_day": 1.5,
                    },
                ]
            },
            "affordable_plan": None,
        }

        result = await run_homewatt_workflow(
            user_id=1,
            session_id=99,
            message="Which appliance should I reduce first?",
            previous_plan=previous_plan,
        )

        self.assertEqual(result["state"]["intent"], "plan_followup")
        self.assertIn("table lamp", result["answer"])
        self.assertIn("Reduce unnecessary table lamp usage first", result["answer"])

    async def test_unsupported_request_stops_before_planning(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message="Tell me a joke",
        )

        self.assertFalse(result["state"]["is_valid"])
        self.assertIn("Sri Lankan domestic electricity tariffs", result["answer"])
        self.assertNotIn("usage_plan", result["state"])

    async def test_incomplete_free_text_plan_requires_form(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message=(
                "My maximum budget is Rs. 600 for May 2026. I need TV 100W, "
                "iron 1000W for 0.25 hours/day, and water motor 750W for "
                "1.5 hours/day."
            ),
        )

        self.assertEqual(result["state"]["intent"], "form_required")
        self.assertIn("add your appliances in the table first", result["answer"])
        self.assertNotIn("usage_plan", result["state"])


if __name__ == "__main__":
    unittest.main()
