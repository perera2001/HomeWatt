"""Small process-local conversation store for HomeWatt sessions."""

import asyncio
import time
from copy import deepcopy
from typing import Any, TypedDict


MAX_MESSAGES = 12
SESSION_TTL_SECONDS = 2 * 60 * 60


class SessionMemory(TypedDict):
    messages: list[dict[str, str]]
    last_successful_plan: dict[str, Any] | None
    updated_at: float


# Local/demo storage only: this is lost on restart and is not shared by workers.
_sessions: dict[tuple[int, int], SessionMemory] = {}
_memory_lock = asyncio.Lock()


def _remove_expired_sessions(now: float) -> None:
    expired_keys = [
        key
        for key, memory in _sessions.items()
        if now - memory["updated_at"] >= SESSION_TTL_SECONDS
    ]
    for key in expired_keys:
        del _sessions[key]


def _new_memory(now: float) -> SessionMemory:
    return {
        "messages": [],
        "last_successful_plan": None,
        "updated_at": now,
    }


async def get_session_memory(user_id: int, session_id: int) -> SessionMemory | None:
    """Return an isolated snapshot of unexpired session memory."""
    async with _memory_lock:
        now = time.monotonic()
        _remove_expired_sessions(now)
        memory = _sessions.get((user_id, session_id))
        return deepcopy(memory) if memory is not None else None


async def append_conversation_turn(
    user_id: int,
    session_id: int,
    user_message: str,
    assistant_message: str,
) -> None:
    """Append one user/assistant turn while keeping history bounded."""
    async with _memory_lock:
        now = time.monotonic()
        _remove_expired_sessions(now)
        key = (user_id, session_id)
        memory = _sessions.get(key, _new_memory(now))
        messages = [
            *memory["messages"],
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ][-MAX_MESSAGES:]
        _sessions[key] = {
            "messages": deepcopy(messages),
            "last_successful_plan": deepcopy(memory["last_successful_plan"]),
            "updated_at": now,
        }


async def save_successful_plan(
    user_id: int,
    session_id: int,
    plan: dict[str, Any],
) -> None:
    """Save a safe plan snapshot without exposing mutable references."""
    async with _memory_lock:
        now = time.monotonic()
        _remove_expired_sessions(now)
        key = (user_id, session_id)
        memory = _sessions.get(key, _new_memory(now))
        _sessions[key] = {
            "messages": deepcopy(memory["messages"]),
            "last_successful_plan": deepcopy(plan),
            "updated_at": now,
        }


async def clear_session_memory(user_id: int, session_id: int) -> None:
    """Remove one user's session memory if it exists."""
    async with _memory_lock:
        _sessions.pop((user_id, session_id), None)
