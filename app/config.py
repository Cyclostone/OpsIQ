"""OpsIQ configuration — loaded from .env or environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

# Project root = opsiq/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STORAGE_DIR = PROJECT_ROOT / "storage"


class Settings(BaseSettings):
    # --- LLM (Groq preferred — free & fast; OpenAI as fallback) ---
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Server ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    # --- Helpers ---
    @property
    def llm_available(self) -> bool:
        return bool(self.groq_api_key) or bool(self.openai_api_key)

    @property
    def llm_provider(self) -> str:
        """Return 'groq', 'openai', or 'none'."""
        if self.groq_api_key:
            return "groq"
        if self.openai_api_key:
            return "openai"
        return "none"


# Singleton
settings = Settings()
