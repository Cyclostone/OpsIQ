"""Tests for OpsIQ configuration and API key availability logic."""

import pytest


class TestConfigSettings:
    """Test that settings are loaded correctly."""

    def test_default_server_settings(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")

        from app.config import Settings
        s = Settings()
        assert s.backend_host == "0.0.0.0"
        assert s.backend_port == 8000


class TestLLMConfig:
    """Test LLM provider selection logic."""

    def test_groq_preferred(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        monkeypatch.setenv("OPENAI_API_KEY", "sk_test")

        from app.config import Settings
        s = Settings()
        assert s.llm_provider == "groq"
        assert s.llm_available is True

    def test_openai_fallback(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "sk_test")

        from app.config import Settings
        s = Settings()
        assert s.llm_provider == "openai"
        assert s.llm_available is True

    def test_no_llm(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")

        from app.config import Settings
        s = Settings()
        assert s.llm_provider == "none"
        assert s.llm_available is False

    def test_default_models(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")

        from app.config import Settings
        s = Settings()
        assert s.groq_model == "llama-3.3-70b-versatile"
        assert s.openai_model == "gpt-4o-mini"
