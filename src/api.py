"""FastAPI service layer.

Run: uvicorn src.api:app --reload

  POST /ask          {"question": "...", "thread_id": "t1"}
  POST /ask/stream   same body -> SSE stream of node events
  GET  /health
  GET  /schema       current database DDL
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import ask, ask_stream
from .db import schema_ddl

app = FastAPI(
    title="bi-analyst-agent",
    version="0.4.0",
    description="LangGraph BI analyst agent service",
)


class AskRequest(BaseModel):
    question: str
    thread_id: str = "default"


class AskResponse(BaseModel):
    question: str
    sql: Optional[str] = None
    answer: Optional[str] = None
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    attempts: int = 0
    chart_path: Optional[str] = None
    error: Optional[str] = None
    trace: list[str] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/schema")
def schema() -> dict:
    return {"ddl": schema_ddl()}


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest) -> AskResponse:
    state = ask(req.question, thread_id=req.thread_id)
    return AskResponse(**{k: v for k, v in state.items() if k in AskResponse.model_fields})


@app.post("/ask/stream")
def ask_stream_endpoint(req: AskRequest) -> StreamingResponse:
    def events():
        for update in ask_stream(req.question, thread_id=req.thread_id):
            for node, delta in update.items():
                payload = {
                    "node": node,
                    "trace": delta.get("trace", []),
                    "answer": delta.get("answer"),
                    "sql": delta.get("sql"),
                }
                yield f"data: {json.dumps(payload, default=str)}\n\n"
        yield "data: {\"node\": \"__done__\"}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
