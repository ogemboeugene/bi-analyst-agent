"""MCP server: exposes the agent as tools any MCP client can call.

  pip install mcp
  python -m src.mcp_server        # stdio transport

Tools:
  ask_bi(question, thread_id) -> sql, answer, rows, trace
  get_schema()                -> current database DDL
"""
from __future__ import annotations

import json

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp >= 2.x
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

from .agent import ask
from .db import schema_ddl

mcp = FastMCP("bi-analyst-agent")


@mcp.tool()
def ask_bi(question: str, thread_id: str = "default") -> str:
    """Ask a natural-language BI question; returns validated SQL + answer."""
    state = ask(question, thread_id=thread_id)
    return json.dumps(
        {
            "sql": state.get("sql"),
            "answer": state.get("answer"),
            "rows": state.get("rows", [])[:20],
            "trace": state.get("trace", []),
        },
        default=str,
    )


@mcp.tool()
def get_schema() -> str:
    """Return the database DDL the agent queries against."""
    return schema_ddl()


if __name__ == "__main__":
    mcp.run()
