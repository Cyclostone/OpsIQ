"""Tests for OpsIQ configuration and API key availability logic."""

import pytest


class TestConfigAvailability:
    """Test that sponsor availability checks work correctly."""

    def test_datadog_needs_both_keys(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "real")
        monkeypatch.setenv("DATADOG_API_KEY", "test_api_key")
        monkeypatch.setenv("DATADOG_APP_KEY", "test_app_key")
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")

        from app.config import Settings
        s = Settings()
        assert s.datadog_available is True

    def test_datadog_unavailable_without_app_key(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "real")
        monkeypatch.setenv("DATADOG_API_KEY", "test_api_key")
        monkeypatch.setenv("DATADOG_APP_KEY", "")

        from app.config import Settings
        s = Settings()
        assert s.datadog_available is False

    def test_datadog_unavailable_without_api_key(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "real")
        monkeypatch.setenv("DATADOG_API_KEY", "")
        monkeypatch.setenv("DATADOG_APP_KEY", "test_app_key")

        from app.config import Settings
        s = Settings()
        assert s.datadog_available is False

    def test_datadog_unavailable_in_mock_mode(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "mock")
        monkeypatch.setenv("DATADOG_API_KEY", "test_api_key")
        monkeypatch.setenv("DATADOG_APP_KEY", "test_app_key")

        from app.config import Settings
        s = Settings()
        assert s.datadog_available is False

    def test_lightdash_available(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "real")
        monkeypatch.setenv("LIGHTDASH_API_KEY", "test_key")

        from app.config import Settings
        s = Settings()
        assert s.lightdash_available is True

    def test_lightdash_unavailable_no_key(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "real")
        monkeypatch.setenv("LIGHTDASH_API_KEY", "")

        from app.config import Settings
        s = Settings()
        assert s.lightdash_available is False

    def test_airia_available(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "real")
        monkeypatch.setenv("AIRIA_API_KEY", "test_key")

        from app.config import Settings
        s = Settings()
        assert s.airia_available is True

    def test_airia_unavailable_no_key(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "real")
        monkeypatch.setenv("AIRIA_API_KEY", "")

        from app.config import Settings
        s = Settings()
        assert s.airia_available is False

    def test_modulate_available_regardless_of_mode(self, monkeypatch):
        monkeypatch.setenv("OPSIQ_MODE", "mock")
        monkeypatch.setenv("MODULATE_API_KEY", "test_key")

        from app.config import Settings
        s = Settings()
        assert s.modulate_available is True

    def test_modulate_unavailable_no_key(self, monkeypatch):
        monkeypatch.setenv("MODULATE_API_KEY", "")

        from app.config import Settings
        s = Settings()
        assert s.modulate_available is False


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
