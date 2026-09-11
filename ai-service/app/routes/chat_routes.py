"""Temporary chat route that exercises the MCP client directly."""
from fastapi import APIRouter, HTTPException

from app.mcp_client.client import MCPClientError, generate_initial_usage_plan_via_mcp
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    message = request.message.lower()
    is_budget_test = "budget" in message and "may" in message and "2026" in message
    if not is_budget_test:
        return ChatResponse(
            answer="AI service is working. Send the May 2026 budget test message to run MCP."
        )

    # Temporary deterministic test path until natural-language parsing and agents exist.
    test_appliances = [
        {"name": "TV", "watts": 100},
        {"name": "Iron", "watts": 1000},
        {"name": "Water motor", "watts": 750},
    ]

    try:
        mcp_result = await generate_initial_usage_plan_via_mcp(
            year=2026,
            month=5,
            max_budget_lkr=3000,
            appliances=test_appliances,
        )
    except MCPClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(
        answer="MCP usage plan generated successfully.",
        mcp_result=mcp_result,
    )
