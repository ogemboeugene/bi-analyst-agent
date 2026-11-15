"""Thin provider-agnostic chat wrapper. Swap provider here only."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import settings

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        if not settings.ai_api_key:
            raise RuntimeError(
                "AI_API_KEY not set. Copy .env.example to .env and add your key."
            )
        _llm = ChatOpenAI(
            model=settings.model,
            temperature=0,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
        )
    return _llm


def chat(system: str, user: str) -> str:
    resp = _get_llm().invoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    return resp.content.strip()


def chat_structured(system: str, user: str, schema):
    """Provider-native structured output (ToolStrategy fallback per model)."""
    return _get_llm().with_structured_output(schema).invoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
