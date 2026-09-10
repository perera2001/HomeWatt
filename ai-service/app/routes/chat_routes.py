"""Chat route placeholder."""
from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return ChatResponse(
        answer="AI service is working. Multi-agent electricity planner will be implemented next."
    )