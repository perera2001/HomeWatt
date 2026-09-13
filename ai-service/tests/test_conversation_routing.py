"""Tests for conversational routing and on-demand MCP Resources."""

import json
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import ToolMessage

from app.agents.appliance_agent import appliance_analyzer_node
from app.agents.information_agent import (
    create_information_agent,
    information_node,
)
from app.agents.supervisor import _fallback_supervisor_decision
from app.agents.tools import (
    read_appliance_priority_rules_tool,
    read_tariff_resource_tool,
)
from app.graph.workflow import run_homewatt_workflow
from app.config import settings
from app.memory.session_memory import (
    append_conversation_turn,
    clear_session_memory,
    get_session_memory,
    save_successful_plan,
)
from tests.test_appliance_agent import ONE_APPLIANCE, _agent_result


TEST_PLAN = {
    "year": 2026,
    "month": 5,
    "max_budget_lkr": 600.0,
    "appliances": ONE_APPLIANCE,
    "appliance_priorities": [
        {
            "item_name": "TV",
            "normalized_name": "tv",
            "priority": "low",
            "category_note": "Optional entertainment load.",
        }
    ],
    "billing_days": 31,
    "estimated_allowed_units": 50.0,
    "requested_plan": {
        "appliances": [
            {
                "name": "TV",
                "watts": 100.0,
                "normalized_name": "tv",
                "priority": "low",
                "required_hours_per_day": 2.0,
            }
        ]
    },
    "affordable_plan": {
        "appliances": [
            {
                "name": "TV",
                "normalized_name": "tv",
                "suggested_hours_per_day": 1.5,
            }
        ]
    },
    "minimum_required_budget": 700.0,
    "minimum_possible_bill": 82.05,
    "budget_shortfall": 100.0,
    "remaining_budget": 0.0,
    "requirements_met": False,
    "budget_feasible": True,
    "estimated_bill": 599.0,
}


def _resource_result(tool_name: str, payload: dict, answer: str) -> dict:
    return {
        "messages": [
            ToolMessage(
                content=json.dumps(payload),
                tool_call_id="resource-call",
                name=tool_name,
            )
        ],
        "structured_response": {"answer": answer},
    }


class ConversationWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_openai_api_key = settings.openai_api_key
        settings.openai_api_key = ""

    def tearDown(self):
        settings.openai_api_key = self.original_openai_api_key

    async def asyncSetUp(self):
        for user_id in (301, 302):
            for session_id in (401, 402, 403):
                await clear_session_memory(user_id, session_id)

    async def test_successful_plan_snapshot_is_saved_from_whitelist(self):
        final_state = {
            "intent": "usage_plan",
            "usage_plan": {"complete": True},
            "final_answer": "plan answer",
            **TEST_PLAN,
            "secret_internal_value": "do not store",
        }
        with patch(
            "app.graph.workflow.homewatt_graph.ainvoke",
            new_callable=AsyncMock,
            return_value=final_state,
        ):
            result = await run_homewatt_workflow(301, 401, "create a plan")

        memory = await get_session_memory(301, 401)
        self.assertEqual(result["answer"], "plan answer")
        self.assertEqual(memory["last_successful_plan"]["year"], 2026)
        self.assertNotIn("secret_internal_value", memory["last_successful_plan"])
        self.assertEqual(len(memory["messages"]), 2)

    async def test_followup_uses_latest_successful_plan(self):
        await save_successful_plan(301, 401, TEST_PLAN)

        result = await run_homewatt_workflow(
            301, 401, "How can I decrease my bill?"
        )

        self.assertEqual(result["state"]["intent"], "plan_followup")
        self.assertIn("TV", result["answer"])
        self.assertIn("2 required hours/day", result["answer"])
        self.assertIn("1.5 suggested hours/day", result["answer"])

    async def test_followup_without_plan_requests_a_plan(self):
        result = await run_homewatt_workflow(
            301, 402, "How can I decrease my bill?"
        )

        self.assertIn("Please create a usage plan first", result["answer"])

    async def test_failed_request_preserves_successful_plan(self):
        await save_successful_plan(301, 401, TEST_PLAN)

        await run_homewatt_workflow(301, 401, "Tell me a joke")

        memory = await get_session_memory(301, 401)
        self.assertEqual(memory["last_successful_plan"], TEST_PLAN)

    @patch("app.graph.workflow.append_conversation_turn", new_callable=AsyncMock)
    async def test_none_session_does_not_store_memory(self, append_turn):
        result = await run_homewatt_workflow(301, None, "hello")

        self.assertEqual(result["answer"], "Hi, how can I assist you today?")
        append_turn.assert_not_awaited()

    async def test_out_of_scope_and_greeting_do_not_call_domain_nodes(self):
        with patch(
            "app.agents.appliance_agent.appliance_analyzer_node",
            new_callable=AsyncMock,
        ) as appliance, patch(
            "app.agents.information_agent.information_node",
            new_callable=AsyncMock,
        ) as information:
            greeting = await run_homewatt_workflow(301, 401, "hello")
            out_of_scope = await run_homewatt_workflow(301, 401, "Tell me a joke")

        self.assertEqual(greeting["state"]["intent"], "greeting")
        self.assertEqual(out_of_scope["state"]["intent"], "out_of_scope")
        appliance.assert_not_awaited()
        information.assert_not_awaited()


class SupervisorRoutingTests(unittest.TestCase):
    def test_fallback_supports_all_intents(self):
        cases = {
            "hello": "greeting",
            "My budget is LKR 5000 for September 2026.": "usage_plan",
            "How can I decrease my bill?": "plan_followup",
            "How can I generally reduce my household electricity bill?": "general_saving_advice",
            "How is a Sri Lankan domestic bill calculated?": "tariff_information",
            "Which appliance types are normally reduced first?": "priority_information",
            "Tell me a joke": "out_of_scope",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                decision = _fallback_supervisor_decision(message)
                self.assertEqual(decision.intent, expected)
                self.assertEqual(
                    decision.is_valid_request,
                    expected != "out_of_scope",
                )


class ApplianceConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_new_plan_does_not_receive_stale_context(self):
        message = "My budget is Rs. 600 for May 2026. TV 100W for 2 hours/day."
        with patch(
            "app.agents.appliance_agent.has_openai_config", return_value=True
        ), patch(
            "app.agents.appliance_agent.create_appliance_analyzer_agent"
        ) as create_agent:
            create_agent.return_value.ainvoke = AsyncMock(
                return_value=_agent_result(ONE_APPLIANCE)
            )
            await appliance_analyzer_node(
                {
                    "message": message,
                    "conversation_history": [
                        {"role": "user", "content": "Old unrelated plan"}
                    ],
                    "previous_plan": TEST_PLAN,
                }
            )

        sent_messages = create_agent.return_value.ainvoke.await_args.args[0]["messages"]
        self.assertEqual(sent_messages, [{"role": "user", "content": message}])

    async def test_incremental_hours_receive_previous_tv_context(self):
        history = [
            {"role": "user", "content": "My TV is 100W."},
            {
                "role": "assistant",
                "content": "Please enter required hours per day for TV.",
            },
        ]
        with patch(
            "app.agents.appliance_agent.has_openai_config", return_value=True
        ), patch(
            "app.agents.appliance_agent.create_appliance_analyzer_agent"
        ) as create_agent:
            create_agent.return_value.ainvoke = AsyncMock(
                return_value=_agent_result(ONE_APPLIANCE)
            )
            state = await appliance_analyzer_node(
                {
                    "message": "2 hours per day.",
                    "conversation_history": history,
                    "previous_plan": None,
                }
            )

        sent_messages = create_agent.return_value.ainvoke.await_args.args[0]["messages"]
        self.assertEqual(sent_messages[0], history[0])
        self.assertEqual(sent_messages[-1]["content"], "2 hours per day.")
        self.assertEqual(state["appliances"], ONE_APPLIANCE)

    async def test_current_explicit_value_overrides_previous_plan_result(self):
        updated = [{**ONE_APPLIANCE[0], "required_hours_per_day": 1.0}]
        previous = {**TEST_PLAN, "appliances": ONE_APPLIANCE}
        with patch(
            "app.agents.appliance_agent.has_openai_config", return_value=True
        ), patch(
            "app.agents.appliance_agent.create_appliance_analyzer_agent"
        ) as create_agent:
            create_agent.return_value.ainvoke = AsyncMock(
                return_value=_agent_result(updated)
            )
            state = await appliance_analyzer_node(
                {
                    "message": "Change my TV usage to 1 hour/day.",
                    "conversation_history": [],
                    "previous_plan": previous,
                }
            )

        self.assertEqual(state["appliances"][0]["required_hours_per_day"], 1.0)


class InformationAgentTests(unittest.IsolatedAsyncioTestCase):
    @patch("app.agents.information_agent.create_chat_model")
    @patch("app.agents.information_agent.create_agent")
    def test_each_intent_registers_only_its_resource_tool(
        self, create_agent, create_chat_model
    ):
        create_chat_model.return_value = object()

        create_information_agent("tariff_information")
        tariff_tools = create_agent.call_args.kwargs["tools"]
        create_information_agent("priority_information")
        priority_tools = create_agent.call_args.kwargs["tools"]

        self.assertEqual([tool.name for tool in tariff_tools], [read_tariff_resource_tool.name])
        self.assertEqual(
            [tool.name for tool in priority_tools],
            [read_appliance_priority_rules_tool.name],
        )

    async def _run_information(self, intent, result):
        with patch(
            "app.agents.information_agent.has_openai_config", return_value=True
        ), patch(
            "app.agents.information_agent.create_information_agent"
        ) as create_agent:
            create_agent.return_value.ainvoke = AsyncMock(return_value=result)
            state = await information_node({"intent": intent, "message": "question"})
        return state

    async def test_tariff_question_accepts_only_tariff_resource_result(self):
        state = await self._run_information(
            "tariff_information",
            _resource_result(
                read_tariff_resource_tool.name,
                {"tariff_version": "2026-05"},
                "The tariff version is 2026-05.",
            ),
        )
        self.assertEqual(state["final_answer"], "The tariff version is 2026-05.")

    async def test_priority_question_accepts_only_priority_resource_result(self):
        state = await self._run_information(
            "priority_information",
            _resource_result(
                read_appliance_priority_rules_tool.name,
                {"TV": {"priority": "low"}},
                "TV is normally low priority.",
            ),
        )
        self.assertEqual(state["final_answer"], "TV is normally low priority.")

    async def test_wrong_resource_result_is_rejected(self):
        state = await self._run_information(
            "tariff_information",
            _resource_result(
                read_appliance_priority_rules_tool.name,
                {"TV": {"priority": "low"}},
                "wrong answer",
            ),
        )
        self.assertIn("Could not verify", state["final_answer"])


if __name__ == "__main__":
    unittest.main()
