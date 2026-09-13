"""Chat route for the HomeWatt Advisor workflow."""
from fastapi import APIRouter, Depends

from app.graph.workflow import run_homewatt_workflow
from app.security.internal_auth import verify_internal_token
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    response_model_exclude_none=True,
)
async def chat(
    request: ChatRequest,
    _: None = Depends(verify_internal_token),
):
    result = await run_homewatt_workflow(
        user_id=request.user_id,
        session_id=request.session_id,
        message=request.message,
        year=request.year,
        month=request.month,
        max_budget_lkr=request.max_budget_lkr,
        appliances=(
            [appliance.model_dump() for appliance in request.appliances]
            if request.appliances is not None
            else None
        ),
        previous_plan=request.previous_plan,
    )
    return ChatResponse(
        answer=result["answer"],
        plan_snapshot=(
            result.get("plan_snapshot")
            if request.include_plan_snapshot
            else None
        ),
    )
