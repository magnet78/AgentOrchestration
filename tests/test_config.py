import os
import pytest
from src.common.config import Config, ALLOWED_CONFIG_KEYS


class TestConfig:
    def test_load_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"app": {"name": "test", "port": 8080}}')
        config = Config(str(config_file))
        assert config.get("app.name") == "test"
        assert config.get("app.port") == 8080

    def test_load_yaml_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("app:\n  name: yaml-test\n  port: 9090\n")
        config = Config(str(config_file))
        assert config.get("app.name") == "yaml-test"
        assert config.get("app.port") == 9090

    def test_default_value(self):
        config = Config()
        assert config.get("nonexistent.key", "default") == "default"

    def test_set_value(self):
        config = Config()
        config.set("database.host", "localhost")
        assert config.get("database.host") == "localhost"

    def test_nested_set(self):
        config = Config()
        config.set("a.b.c.d", "value")
        assert config.get("a.b.c.d") == "value"

    def test_to_dict(self):
        config = Config()
        config.set("key1", "value1")
        config.set("key2", "value2")
        data = config.to_dict()
        assert data["key1"] == "value1"
        assert data["key2"] == "value2"

    def test_env_overrides_respect_allowlist(self, monkeypatch):
        """Only allowed AO_ env vars should be imported as config overrides."""
        monkeypatch.setenv("AO_APP_NAME", "overridden")
        monkeypatch.setenv("AO_AGENT_ID", "should-not-appear")
        monkeypatch.setenv("AO_UNKNOWN_VAR", "also-hidden")
        config = Config()
        assert config.get("app.name") == "overridden"
        assert config.get("agent.id") is None
        assert config.get("unknown.var") is None
        # Clean up
        monkeypatch.delenv("AO_APP_NAME", raising=False)
        monkeypatch.delenv("AO_AGENT_ID", raising=False)
        monkeypatch.delenv("AO_UNKNOWN_VAR", raising=False)

    def test_env_overrides_with_custom_allowlist(self, monkeypatch):
        """Custom allowlist should override the default."""
        monkeypatch.setenv("AO_CUSTOM_KEY", "custom_value")
        config = Config()
        config._load_env_overrides(allowed_keys={"CUSTOM.KEY"})
        assert config.get("custom.key") == "custom_value"
        monkeypatch.delenv("AO_CUSTOM_KEY", raising=False)

    def test_allowed_config_keys_is_frozenset(self):
        """Allowlist should be a frozenset for safety."""
        assert isinstance(ALLOWED_CONFIG_KEYS, frozenset)
        assert len(ALLOWED_CONFIG_KEYS) > 0
