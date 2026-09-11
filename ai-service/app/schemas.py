"""Request and response schemas."""
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int
    session_id: int | None = None
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    mcp_result: dict[str, Any] | list[Any] | str | None = None
