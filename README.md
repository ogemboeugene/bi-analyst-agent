# bi-analyst-agent

A LangGraph BI analyst agent: ask questions in plain English, get validated SQL,
executed results, charts, and a written explanation — with agent memory,
guardrails, and measured accuracy. Built as the standalone research version of
conversational-BI techniques I ship in production.

## Architecture

```mermaid
graph TD
    Q[question] --> RQ[resolve_question<br/>rewrite follow-ups via history]
    RQ --> P[plan]
    P --> G[generate_sql<br/>structured output + few-shot exemplars]
    G --> V[validate<br/>sqlglot parse · read-only · LIMIT · EXPLAIN]
    V -->|guardrail/plan error| SC
    V --> E[execute<br/>DuckDB]
    E -->|exec error| SC[self_correct<br/>error fed back, max 3]
    SC --> V
    E --> C[chart<br/>matplotlib, skipped when unsuitable]
    C --> N[narrate<br/>stakeholder answer]
    N --> M[remember<br/>save verified Q→SQL to memory]
    M --> END((END))
    V -->|retries exhausted| F[fail: honest dead-end]
    E -->|retries exhausted| F
    F --> END
```

10-node `StateGraph`, `MemorySaver` checkpointer for multi-turn conversations,
conditional retry edges, `stream_mode="updates"` for live node events.

## Why not just use vanna?

The seed notebook (`notebooks/quickstart.ipynb`) ships vanna 2.x — a hosted
agent framework. This repo is a deliberate from-scratch LangGraph
implementation of the same problem, which makes different trade-offs:

| | vanna 2.x quickstart | this repo |
|---|---|---|
| Agent loop | hidden in framework | explicit `StateGraph` you can read end-to-end |
| Memory | `DemoAgentMemory` (closed demo) | `exemplars.py` — JSONL store, token-ranked few-shot, auto-save on verified success |
| Guardrails | tool-level | sqlglot parse-level: single statement, read-only anywhere in the tree, auto-LIMIT (incl. CTEs), EXPLAIN-before-run |
| Eval | none | 12-question golden set, execution accuracy, per-category breakdown, run history |
| Observability | built-in UI | LangSmith-ready (env-gated) + per-run node trace |
| Tests | none | 27 pytest cases incl. end-to-end graph runs |

## Quickstart

```bash
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # add OPENAI_API_KEY

python -m src.cli "total revenue by country in 2025"
python -m src.cli "and by segment?" --thread demo        # follow-up uses memory
python -m src.cli "monthly revenue trend" --stream       # live node events
python -m src.eval_harness                               # accuracy on golden set
uvicorn src.api:app --reload                             # POST /ask, /ask/stream (SSE), /schema, /health
pytest -q                                                # 31 tests
```

## Design notes

- **Deterministic pipeline over free ReAct loop** — text-to-SQL wants
  plan→generate→validate→execute→correct, not an open-ended tool loop. The
  graph encodes that; the LLM only fills the nodes.
- **Memory is the accuracy lever** — models imitate verified prior answers
  better than they extrapolate from DDL. Verified pairs are persisted and
  retrieved by question similarity (`data/exemplars.jsonl` ships seeded).
- **Guardrails run before execution** — sqlglot parse (not regex), EXPLAIN
  before run, LIMIT injected even inside CTEs.
- **Honest failure** — after retries the agent reports the last error instead
  of hallucinating a number.

## Observability

Set `LANGSMITH_API_KEY` + `LANGSMITH_TRACING=true` in `.env` for full LangSmith
tracing of every node and LLM call.

## Roadmap

- [x] vanna quickstart seed imported
- [x] LangGraph agent loop (plan → generate → validate → execute → correct → chart → narrate)
- [x] Schema RAG (per-table DDL retrieval)
- [x] Parse-level guardrails (read-only, LIMIT, EXPLAIN)
- [x] Agent memory (exemplar few-shot + auto-save)
- [x] Structured output (`with_structured_output` + Pydantic)
- [x] Conversation memory (`MemorySaver` + follow-up resolution)
- [x] Eval harness (execution accuracy + categories + history)
- [x] Streaming (`--stream`) + pytest suite
- [x] FastAPI service layer (`/ask`, `/ask/stream` SSE, `/schema`, `/health`)
- [ ] Stretch: QLoRA fine-tuned small model vs API baseline

## License

MIT. Seed notebook: vanna-ai/vanna (MIT).
