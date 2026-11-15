"""Runtime configuration via environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("AGENT_MODEL", "gpt-4o-mini")
    db_path: str = os.getenv("AGENT_DB_PATH", "demo.duckdb")
    max_rows: int = int(os.getenv("AGENT_MAX_ROWS", "200"))
    max_attempts: int = int(os.getenv("AGENT_MAX_ATTEMPTS", "3"))
    output_dir: str = os.getenv("AGENT_OUTPUT_DIR", "output")


settings = Settings()
