import pytest
from src.common.config import Config


class TestConfig:
    def test_load_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"app": {"name": "test", "port": 8080}}')
        config = Config(str(config_file))
        assert config.get("app.name") == "test"
        assert config.get("app.port") == 8080

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

    def test_load_yaml_config(self, tmp_path):
        """Test loading YAML config files."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("app:\n  name: yaml-test\n  port: 9090\n")
        config = Config(str(yaml_file))
        assert config.get("app.name") == "yaml-test"
        assert config.get("app.port") == "9090"

    def test_load_yml_extension(self, tmp_path):
        """Test loading .yml extension files."""
        yml_file = tmp_path / "config.yml"
        yml_file.write_text("database:\n  host: localhost\n  port: 5432\n")
        config = Config(str(yml_file))
        assert config.get("database.host") == "localhost"
        assert config.get("database.port") == "5432"

    def test_unsupported_format_raises(self, tmp_path):
        """Test that unsupported file formats raise ValueError."""
        txt_file = tmp_path / "config.txt"
        txt_file.write_text("some config data")
        config = Config()
        import pytest
        with pytest.raises(ValueError, match="Unsupported config file format"):
            config.load(str(txt_file))

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        """Test that empty YAML files return empty dict."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        config = Config(str(yaml_file))
        assert config.to_dict() == {}
