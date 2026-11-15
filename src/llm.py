"""Thin provider-agnostic chat wrapper. Swap provider here only."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import settings

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Copy .env.example to .env and add your key."
            )
        _llm = ChatOpenAI(model=settings.model, temperature=0)
    return _llm


def chat(system: str, user: str) -> str:
    resp = _get_llm().invoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    return resp.content.strip()
