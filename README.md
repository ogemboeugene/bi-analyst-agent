# bi-analyst-agent

A LangGraph BI analyst agent: ask questions in plain English, get validated SQL,
executed results, charts, and a written explanation. Built as the standalone
research version of the conversational-BI techniques I ship in production.

## Status

Phase 1: foundation. `notebooks/quickstart.ipynb` is the seed (from
[vanna-ai/vanna](https://github.com/vanna-ai/vanna), MIT), being rebuilt into a
proper agent loop in `src/`.

## Roadmap

- [x] Import vanna quickstart notebook as baseline
- [x] LangGraph agent loop: plan → schema-retrieve → generate → validate → execute → self-correct → chart → narrate (`src/agent.py`)
- [x] Schema RAG: per-table DDL docs ranked by question relevance (`src/schema_rag.py`)
- [x] Guardrails: single-statement read-only enforcement via sqlglot, auto-LIMIT, EXPLAIN-first (`src/guardrails.py`)
- [ ] Eval harness: golden question set, execution-accuracy scoring (defog-ai/sql-eval methodology)
- [ ] FastAPI service layer
- [ ] Stretch: QLoRA fine-tuned small model vs API baseline, honestly compared

## License

MIT. Seed notebook credit: vanna-ai/vanna (MIT).
