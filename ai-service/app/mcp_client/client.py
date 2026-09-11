"""Small MCP client helpers for the HomeWatt Advisor AI service."""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.config import settings


class MCPClientError(RuntimeError):
    """Raised when the MCP server or a tool call cannot be completed."""


def _get_server_path() -> Path:
    configured_path = Path(settings.mcp_server_path)
    if configured_path.is_absolute():
        return configured_path
    return Path.cwd() / configured_path


def _get_project_root(server_path: Path) -> Path:
    configured_path = Path(settings.mcp_server_path)
    if configured_path.is_absolute():
        return server_path.parent.parent
    return Path.cwd()


@asynccontextmanager
async def create_mcp_session() -> AsyncIterator[ClientSession]:
    """Start the local MCP server over stdio and yield an initialized session."""
    server_path = _get_server_path()
    if not server_path.exists():
        raise MCPClientError(f"MCP server file was not found: {server_path}")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env={
            **os.environ,
            "PYTHONPATH": str(_get_project_root(server_path)),
        },
        cwd=_get_project_root(server_path),
    )

    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
    except MCPClientError:
        raise
    except Exception as exc:
        raise MCPClientError(f"Could not start or connect to MCP server: {exc}") from exc


def _parse_text_if_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _extract_content_item(item: Any) -> Any:
    text = getattr(item, "text", None)
    if text is not None:
        return _parse_text_if_json(text)

    data = getattr(item, "data", None)
    if data is not None:
        return data

    return str(item)


def extract_mcp_content(response: Any) -> Any:
    """Convert MCP SDK response objects into plain Python data."""
    if hasattr(response, "content"):
        content = response.content
        values = [_extract_content_item(item) for item in content]
        if len(values) == 1:
            return values[0]
        return values

    if hasattr(response, "contents"):
        contents = response.contents
        values = [_extract_content_item(item) for item in contents]
        if len(values) == 1:
            return values[0]
        return values

    if hasattr(response, "messages"):
        messages = []
        for message in response.messages:
            content = getattr(message, "content", message)
            messages.append(_extract_content_item(content))
        if len(messages) == 1:
            return messages[0]
        return "\n".join(str(message) for message in messages)

    return response


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Call an MCP tool and return readable data instead of raw SDK objects."""
    try:
        async with create_mcp_session() as session:
            result = await session.call_tool(tool_name, arguments)
            if getattr(result, "isError", False):
                raise MCPClientError(f"MCP tool '{tool_name}' returned an error.")
            return extract_mcp_content(result)
    except MCPClientError:
        raise
    except Exception as exc:
        raise MCPClientError(f"MCP tool '{tool_name}' failed: {exc}") from exc


async def read_mcp_resource(uri: str) -> Any:
    """Read an MCP resource and return parsed JSON when possible."""
    try:
        async with create_mcp_session() as session:
            result = await session.read_resource(uri)
            return extract_mcp_content(result)
    except MCPClientError:
        raise
    except Exception as exc:
        raise MCPClientError(f"MCP resource '{uri}' failed: {exc}") from exc


async def read_tariff_resource_via_mcp() -> dict[str, Any]:
    return await read_mcp_resource("tariff://sri-lanka/domestic/2026-05")


async def read_appliance_priority_rules_via_mcp() -> dict[str, Any]:
    return await read_mcp_resource("appliances://priority-rules")


async def get_mcp_prompt(prompt_name: str, arguments: dict[str, Any]) -> str:
    """Fetch an MCP prompt and return it as text."""
    try:
        async with create_mcp_session() as session:
            result = await session.get_prompt(prompt_name, arguments)
            content = extract_mcp_content(result)
            if isinstance(content, str):
                return content
            return json.dumps(content, indent=2)
    except MCPClientError:
        raise
    except Exception as exc:
        raise MCPClientError(f"MCP prompt '{prompt_name}' failed: {exc}") from exc


async def calculate_domestic_bill_via_mcp(
    year: int, month: int, units: float
) -> dict[str, Any]:
    return await call_mcp_tool(
        "calculate_domestic_bill",
        {"year": year, "month": month, "units": units},
    )


async def generate_initial_usage_plan_via_mcp(
    year: int,
    month: int,
    max_budget_lkr: float,
    appliances: list[dict[str, Any]],
) -> dict[str, Any]:
    return await call_mcp_tool(
        "generate_initial_usage_plan",
        {
            "year": year,
            "month": month,
            "max_budget_lkr": max_budget_lkr,
            "appliances": appliances,
        },
    )


async def calculate_budget_unit_limit_via_mcp(
    year: int, month: int, max_budget_lkr: float
) -> dict[str, Any]:
    return await call_mcp_tool(
        "calculate_budget_unit_limit",
        {"year": year, "month": month, "max_budget_lkr": max_budget_lkr},
    )


async def classify_appliance_priority_via_mcp(item_name: str) -> dict[str, Any]:
    return await call_mcp_tool(
        "classify_appliance_priority",
        {"item_name": item_name},
    )


async def calculate_appliance_kwh_via_mcp(
    watts: float, hours_per_day: float, days: int
) -> dict[str, Any]:
    return await call_mcp_tool(
        "calculate_appliance_kwh",
        {"watts": watts, "hours_per_day": hours_per_day, "days": days},
    )
