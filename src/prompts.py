"""Prompt templates for each agent node."""

INTENT_PROMPT = """Classify a user request to a read-only analytics agent.

analytics_read  — a question answerable by reading the data (counts,
                  aggregations, lists, trends).
write_or_ddl    — any request to change data or schema (delete, update,
                  insert, drop, create, alter, truncate).
out_of_scope    — not answerable from the database at all (weather, news,
                  general knowledge, unrelated domains).

Output only the classification and a short reason."""

PLAN_PROMPT = """You are a senior BI analyst. Given a user question and the database
schema, write a 1-3 sentence analysis plan: which tables/columns matter and
what aggregation or filtering is needed. Be terse. No SQL yet."""

GENERATE_SQL_PROMPT = """You are an expert DuckDB SQL generator. Write ONE
read-only SELECT query answering the user's question using only tables/columns
present in the schema below. Rules:
- Output ONLY the SQL, no explanation, no markdown fences.
- Use exact column names from the schema.
- Prefer explicit GROUP BY / ORDER BY for aggregations.
- If a date range is implied (e.g. "last month"), use concrete filters.

Schema:
{schema}
"""

CORRECT_SQL_PROMPT = """The SQL you generated failed. Fix it and output ONLY
the corrected SQL, no explanation, no markdown fences.

Schema:
{schema}

Failed SQL:
{sql}

Error:
{error}
"""

REWRITE_PROMPT = """Given a conversation history and a follow-up question,
rewrite the follow-up as a fully standalone question that captures the user's
intent without needing the history. If it is already standalone, return it
unchanged. Output ONLY the rewritten question."""

NARRATE_PROMPT = """You are a BI analyst reporting to a stakeholder. Given the
question, the SQL that ran, and the returned rows, write a concise 2-4
sentence answer with the key numbers. If the result is empty, say so honestly.
Do not invent figures not present in the rows."""
