"""Tests for bounded process-local conversation memory."""

import unittest
from unittest.mock import patch

from app.memory.session_memory import (
    MAX_MESSAGES,
    SESSION_TTL_SECONDS,
    append_conversation_turn,
    clear_session_memory,
    get_session_memory,
    save_successful_plan,
)


class SessionMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        for user_id in (101, 102):
            for session_id in (201, 202):
                await clear_session_memory(user_id, session_id)

    async def test_memory_is_keyed_by_user_and_session(self):
        await append_conversation_turn(101, 201, "user one", "answer one")
        await append_conversation_turn(102, 201, "user two", "answer two")
        await append_conversation_turn(101, 202, "other session", "other answer")

        first = await get_session_memory(101, 201)
        second_user = await get_session_memory(102, 201)
        second_session = await get_session_memory(101, 202)

        self.assertEqual(first["messages"][0]["content"], "user one")
        self.assertEqual(second_user["messages"][0]["content"], "user two")
        self.assertEqual(second_session["messages"][0]["content"], "other session")

    async def test_returned_values_are_copies(self):
        plan = {"appliances": [{"name": "TV"}]}
        await save_successful_plan(101, 201, plan)
        memory = await get_session_memory(101, 201)
        memory["last_successful_plan"]["appliances"][0]["name"] = "changed"

        stored = await get_session_memory(101, 201)
        self.assertEqual(stored["last_successful_plan"]["appliances"][0]["name"], "TV")

    async def test_message_history_is_bounded(self):
        for index in range(8):
            await append_conversation_turn(
                101, 201, f"user {index}", f"assistant {index}"
            )

        memory = await get_session_memory(101, 201)
        self.assertEqual(len(memory["messages"]), MAX_MESSAGES)
        self.assertEqual(memory["messages"][0]["content"], "user 2")

    async def test_expired_memory_is_removed(self):
        with patch("app.memory.session_memory.time.monotonic", return_value=10.0):
            await append_conversation_turn(101, 201, "hello", "hi")
        with patch(
            "app.memory.session_memory.time.monotonic",
            return_value=10.0 + SESSION_TTL_SECONDS,
        ):
            memory = await get_session_memory(101, 201)

        self.assertIsNone(memory)


if __name__ == "__main__":
    unittest.main()
