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
    # --- Mode ---
    opsiq_mode: str = Field(default="mock", description="mock or real")

    # --- LLM (Groq preferred — free & fast; OpenAI as fallback) ---
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Datadog ---
    datadog_api_key: str = ""
    datadog_app_key: str = ""
    datadog_site: str = "datadoghq.com"

    # --- Lightdash ---
    lightdash_url: str = ""
    lightdash_api_key: str = ""
    lightdash_project_uuid: str = ""

    # --- Airia ---
    airia_api_url: str = "https://api.airia.ai"
    airia_api_key: str = ""

    # --- Modulate (ToxMod) ---
    modulate_api_key: str = ""
    modulate_api_url: str = "https://api.modulate.ai"

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
    def datadog_available(self) -> bool:
        return self.opsiq_mode == "real" and bool(self.datadog_api_key) and bool(self.datadog_app_key)

    @property
    def lightdash_available(self) -> bool:
        return self.opsiq_mode == "real" and bool(self.lightdash_api_key)

    @property
    def airia_available(self) -> bool:
        return self.opsiq_mode == "real" and bool(self.airia_api_key)

    @property
    def modulate_available(self) -> bool:
        return bool(self.modulate_api_key)

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
