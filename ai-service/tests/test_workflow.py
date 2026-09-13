"""Tests for the HomeWatt LangGraph workflow."""

import json
import unittest
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.graph.workflow import run_homewatt_workflow
from app.memory.session_memory import clear_session_memory
from tests.test_appliance_agent import THREE_APPLIANCES, _agent_result


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

    async def test_budget_message_creates_usage_plan(self):
        with patch(
            "app.agents.appliance_agent.has_openai_config", return_value=True
        ), patch(
            "app.agents.appliance_agent.create_appliance_analyzer_agent"
        ) as create_agent, patch(
            "app.agents.tools.read_tariff_resource_via_mcp",
            new_callable=AsyncMock,
        ) as read_tariff, patch(
            "app.agents.tools.read_appliance_priority_rules_via_mcp",
            new_callable=AsyncMock,
        ) as read_priorities:
            agent_result = _agent_result(THREE_APPLIANCES)
            validation = json.loads(agent_result["messages"][0].content)
            validation["max_budget_lkr"] = 3000.0
            agent_result["messages"][0].content = json.dumps(validation)
            create_agent.return_value.ainvoke = AsyncMock(return_value=agent_result)
            result = await run_homewatt_workflow(
                user_id=1,
                session_id=1,
                message=(
                    "My budget is Rs. 3000 for May 2026. "
                    "I need TV 100W for 2 hours/day, iron 1000W for 15 minutes/day "
                    "and water motor 750W for 1.5 hours/day."
                ),
            )

        read_tariff.assert_not_awaited()
        read_priorities.assert_not_awaited()

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
        self.assertEqual(state["appliances"][1]["required_hours_per_day"], 0.25)
        self.assertNotIn("tariff_resource", state)
        self.assertNotIn("priority_rules_resource", state)

    async def test_unsupported_request_stops_before_planning(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message="Tell me a joke",
        )

        self.assertFalse(result["state"]["is_valid"])
        self.assertIn("Sri Lankan domestic electricity tariffs", result["answer"])
        self.assertNotIn("usage_plan", result["state"])

    async def test_missing_appliance_hours_returns_simple_message(self):
        result = await run_homewatt_workflow(
            user_id=1,
            session_id=1,
            message=(
                "My maximum budget is Rs. 600 for May 2026. I need TV 100W, "
                "iron 1000W for 0.25 hours/day, and water motor 750W for "
                "1.5 hours/day."
            ),
        )

        self.assertEqual(
            result["answer"],
            "Please enter required hours per day for TV. Example: TV 100W for 2 hours/day.",
        )
        self.assertNotIn("usage_plan", result["state"])


if __name__ == "__main__":
    unittest.main()
