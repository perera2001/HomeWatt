"""Shared LangChain model helpers."""

from langchain_openai import ChatOpenAI

from app.config import settings


def has_openai_config() -> bool:
    """Return True when LLM agents can be called."""
    return bool(settings.openai_api_key.strip())


def create_chat_model() -> ChatOpenAI:
    """Create the configured OpenAI chat model."""
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
    )
