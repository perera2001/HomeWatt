"""Chat route for the HomeWatt Advisor workflow."""
from fastapi import APIRouter, Depends

from app.graph.workflow import run_homewatt_workflow
from app.security.internal_auth import verify_internal_token
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _: None = Depends(verify_internal_token),
):
    result = await run_homewatt_workflow(
        user_id=request.user_id,
        session_id=request.session_id,
        message=request.message,
    )
    return ChatResponse(
        answer=result["answer"],
        mcp_result=result.get("state"),
    )
