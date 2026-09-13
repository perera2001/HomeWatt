"""Focused tests for agent-controlled appliance tools."""

import json
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool

from app.agents.appliance_agent import (
    appliance_analyzer_node,
    create_appliance_analyzer_agent,
)
from app.agents.tools import (
    classify_appliance_priority_tool,
    validate_appliance_input_tool,
)
from app.mcp_client.client import MCPClientError


ONE_APPLIANCE = [
    {"name": "TV", "watts": 100.0, "required_hours_per_day": 2.0},
]
THREE_APPLIANCES = [
    *ONE_APPLIANCE,
    {"name": "iron", "watts": 1000.0, "required_hours_per_day": 0.25},
    {"name": "water motor", "watts": 750.0, "required_hours_per_day": 1.5},
]
PRIORITY_RESULTS = {
    "TV": {
        "item_name": "TV",
        "normalized_name": "tv",
        "priority": "low",
        "category_note": "Optional entertainment load.",
    },
    "iron": {
        "item_name": "iron",
        "normalized_name": "iron",
        "priority": "medium",
        "category_note": "Use briefly.",
    },
    "water motor": {
        "item_name": "water motor",
        "normalized_name": "water motor",
        "priority": "high",
        "category_note": "Protect reasonable usage.",
    },
}
VALID_MESSAGE = "My budget is Rs. 600 for May 2026. TV 100W for 2 hours/day."


def _tool_message(name: str, payload, call_id: str) -> ToolMessage:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return ToolMessage(content=content, tool_call_id=call_id, name=name)


def _agent_result(appliances=ONE_APPLIANCE, messages=None):
    validation = {
        "is_valid": True,
        "errors": [],
        "year": 2026,
        "month": 5,
        "max_budget_lkr": 600.0,
        "appliances": appliances,
    }
    tool_messages = [
        _tool_message(validate_appliance_input_tool.name, validation, "validation"),
        *[
            _tool_message(
                classify_appliance_priority_tool.name,
                PRIORITY_RESULTS[item["name"]],
                f"priority-{index}",
            )
            for index, item in enumerate(appliances)
        ],
    ]
    return {
        "structured_response": {
            "year": 2026,
            "month": 5,
            "max_budget_lkr": 600.0,
            "appliances": appliances,
        },
        "messages": tool_messages if messages is None else messages,
    }


class ApplianceAnalyzerAgentTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, result, message=VALID_MESSAGE):
        with patch(
            "app.agents.appliance_agent.has_openai_config", return_value=True
        ), patch(
            "app.agents.appliance_agent.create_appliance_analyzer_agent"
        ) as create_agent:
            create_agent.return_value.ainvoke = AsyncMock(return_value=result)
            state = await appliance_analyzer_node({"message": message})
        return state, create_agent

    @patch("app.agents.appliance_agent.create_chat_model")
    @patch("app.agents.appliance_agent.create_agent")
    def test_agent_has_only_validation_and_classification_tools(
        self, create_agent, create_chat_model
    ):
        create_chat_model.return_value = object()

        create_appliance_analyzer_agent()

        tools = create_agent.call_args.kwargs["tools"]
        self.assertEqual(
            [tool.name for tool in tools],
            [
                validate_appliance_input_tool.name,
                classify_appliance_priority_tool.name,
            ],
        )

    async def test_valid_request_with_one_appliance(self):
        state, _ = await self._run(_agent_result())
        self.assertNotIn("error", state)
        self.assertEqual(state["appliances"], ONE_APPLIANCE)
        self.assertEqual(state["appliance_priorities"][0]["priority"], "low")

    async def test_valid_request_with_multiple_appliances(self):
        message = (
            "My budget is Rs. 600 for May 2026. TV 100W for 2 hours/day, "
            "iron 1000W for 0.25 hours/day, and water motor 750W for 1.5 hours/day."
        )
        state, _ = await self._run(_agent_result(THREE_APPLIANCES), message)
        self.assertEqual(len(state["appliance_priorities"]), 3)
        self.assertEqual(
            [item["item_name"] for item in state["appliance_priorities"]],
            ["TV", "iron", "water motor"],
        )

    async def test_missing_required_hours_stops_before_agent(self):
        state, create_agent = await self._run(
            _agent_result(),
            "My budget is Rs. 600 for May 2026. TV 100W.",
        )
        self.assertIn("Please enter required hours per day for TV", state["error"])
        create_agent.assert_not_called()

    def test_validation_rejects_invalid_fields(self):
        cases = [
            {"month": 13},
            {"max_budget_lkr": 0},
            {"appliances": [{**ONE_APPLIANCE[0], "watts": 0}]},
            {"appliances": [{**ONE_APPLIANCE[0], "required_hours_per_day": 25}]},
        ]
        for changes in cases:
            values = {
                "year": 2026,
                "month": 5,
                "max_budget_lkr": 600,
                "appliances": ONE_APPLIANCE,
                **changes,
            }
            with self.subTest(changes=changes):
                result = validate_appliance_input_tool.invoke(
                    {
                        "year": values["year"],
                        "month": values["month"],
                        "max_budget_lkr": values["max_budget_lkr"],
                        "appliances_json": json.dumps(values["appliances"]),
                    }
                )
                self.assertFalse(result["is_valid"])

    async def test_validation_tool_error_stops_workflow(self):
        result = _agent_result()
        validation = {
            "is_valid": False,
            "errors": ["budget must be greater than 0"],
            "year": 2026,
            "month": 5,
            "max_budget_lkr": 0,
            "appliances": ONE_APPLIANCE,
        }
        result["messages"][0] = _tool_message(
            validate_appliance_input_tool.name, validation, "validation"
        )
        state, _ = await self._run(result)
        self.assertEqual(
            state["error"],
            "Please correct the following: budget must be greater than 0.",
        )

    async def test_missing_validation_tool_is_rejected(self):
        result = _agent_result()
        result["messages"] = result["messages"][1:]
        state, _ = await self._run(result)
        self.assertIn("did not validate", state["error"])

    async def test_missing_appliance_classification_is_rejected(self):
        result = _agent_result(THREE_APPLIANCES)
        result["messages"] = result["messages"][:-1]
        state, _ = await self._run(result)
        self.assertIn("did not classify water motor", state["error"])

    async def test_duplicate_priority_result_is_rejected(self):
        result = _agent_result()
        result["messages"].append(
            _tool_message(
                classify_appliance_priority_tool.name,
                PRIORITY_RESULTS["TV"],
                "duplicate-priority",
            )
        )
        state, _ = await self._run(result)
        self.assertIn("classified TV more than once", state["error"])

    async def test_malformed_tool_message_is_rejected(self):
        result = _agent_result()
        result["messages"][0] = _tool_message(
            validate_appliance_input_tool.name, "not-json", "validation"
        )
        state, _ = await self._run(result)
        self.assertIn("invalid appliance validation result", state["error"])

    async def test_duplicate_validation_is_rejected(self):
        result = _agent_result()
        result["messages"].append(
            _tool_message(
                validate_appliance_input_tool.name,
                json.loads(result["messages"][0].content),
                "duplicate-validation",
            )
        )
        state, _ = await self._run(result)
        self.assertIn("repeated validate the appliance details", state["error"])

    async def test_mcp_failure_is_controlled(self):
        with patch(
            "app.agents.appliance_agent.has_openai_config", return_value=True
        ), patch(
            "app.agents.appliance_agent.create_appliance_analyzer_agent"
        ) as create_agent:
            create_agent.return_value.ainvoke = AsyncMock(
                side_effect=MCPClientError("server unavailable")
            )
            state = await appliance_analyzer_node({"message": VALID_MESSAGE})
        self.assertEqual(
            state["error"], "Could not complete appliance analysis. Please try again."
        )

    async def test_successful_state_keeps_required_fields(self):
        state, _ = await self._run(_agent_result())
        for field in (
            "year",
            "month",
            "max_budget_lkr",
            "appliances",
            "appliance_priorities",
        ):
            self.assertIn(field, state)

    async def test_node_does_not_manually_call_tools(self):
        with patch.object(StructuredTool, "invoke") as invoke, patch.object(
            StructuredTool, "ainvoke", new_callable=AsyncMock
        ) as ainvoke:
            state, _ = await self._run(_agent_result())
        self.assertNotIn("error", state)
        invoke.assert_not_called()
        ainvoke.assert_not_called()

    async def test_each_appliance_has_exactly_one_classification(self):
        result = _agent_result(THREE_APPLIANCES)
        classification_messages = [
            item
            for item in result["messages"]
            if item.name == classify_appliance_priority_tool.name
        ]
        self.assertEqual(len(classification_messages), len(THREE_APPLIANCES))
        state, _ = await self._run(result)
        self.assertNotIn("error", state)

    async def test_openai_unavailable_returns_controlled_error(self):
        with patch(
            "app.agents.appliance_agent.has_openai_config", return_value=False
        ), patch(
            "app.agents.appliance_agent.create_appliance_analyzer_agent"
        ) as create_agent:
            state = await appliance_analyzer_node({"message": VALID_MESSAGE})
        self.assertIn("analyzer is unavailable", state["error"])
        create_agent.assert_not_called()

    @patch(
        "app.mcp_client.client.read_appliance_priority_rules_via_mcp",
        new_callable=AsyncMock,
    )
    async def test_node_does_not_read_priority_resource(self, read_resource):
        state, _ = await self._run(_agent_result())
        self.assertNotIn("error", state)
        read_resource.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
