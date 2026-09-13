"""Request and response schemas."""
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ChatApplianceInput(BaseModel):
    name: str = Field(min_length=1)
    watts: float = Field(gt=0)
    required_hours_per_day: float = Field(gt=0, le=24)
    priority: Literal["high", "medium", "low"]


class ChatRequest(BaseModel):
    user_id: int
    session_id: int | None = None
    message: str = Field(min_length=1)
    year: int | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    max_budget_lkr: float | None = Field(default=None, gt=0)
    appliances: list[ChatApplianceInput] | None = Field(default=None, min_length=1)
    previous_plan: dict[str, Any] | None = None
    include_plan_snapshot: bool = False

    @model_validator(mode="after")
    def validate_structured_fields(self):
        structured_values = (
            self.year,
            self.month,
            self.max_budget_lkr,
            self.appliances,
        )
        if any(value is not None for value in structured_values) and not all(
            value is not None for value in structured_values
        ):
            raise ValueError(
                "year, month, max_budget_lkr, and appliances are required together"
            )
        return self


class ChatResponse(BaseModel):
    answer: str
    plan_snapshot: dict[str, Any] | None = None
    mcp_result: dict[str, Any] | list[Any] | str | None = None
