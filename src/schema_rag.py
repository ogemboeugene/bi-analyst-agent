"""Schema retrieval: rank table docs by relevance to the question.

Small schemas return everything (fine). For large schemas, per-table docs are
ranked by token overlap; swap `_score` for real embeddings when the schema
outgrows the context window.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .db import schema_ddl
from .semantics import GLOSSARY


@dataclass
class SchemaDoc:
    table: str
    ddl: str
    tokens: set[str]


_TOKEN_RE = re.compile(r"[a-z_]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class SchemaIndex:
    def __init__(self) -> None:
        self.docs = [
            SchemaDoc(
                table=ddl.split("(")[0].split()[-1].strip(),
                ddl=ddl,
                tokens=_tokenize(ddl),
            )
            for ddl in schema_ddl().split("\n\n")
        ]

    def retrieve(self, question: str, k: int = 8) -> str:
        """Return the top-k table DDLs relevant to the question, plus the
        business glossary (semantics are always needed, not ranked)."""
        q_tokens = _tokenize(question)
        if len(self.docs) <= k:
            chosen = self.docs
        else:
            chosen = sorted(
                self.docs,
                key=lambda d: len(d.tokens & q_tokens),
                reverse=True,
            )[:k]
        return "\n\n".join(d.ddl for d in chosen) + "\n\n" + GLOSSARY
