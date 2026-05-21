"""Configuration management module."""

import os
import json
from typing import Any, Dict, Optional, Set


# Allowlist of documented config override keys (without AO_ prefix)
# Only these environment variables will be imported as config overrides by default.
# Runtime-only values (e.g., AO_AGENT_ID) are excluded to prevent leakage into config snapshots.
ALLOWED_CONFIG_KEYS: Set[str] = frozenset({
    "APP.NAME",
    "APP.PORT",
    "APP.HOST",
    "APP.DEBUG",
    "APP.LOG_LEVEL",
    "DATABASE.HOST",
    "DATABASE.PORT",
    "DATABASE.NAME",
    "DATABASE.USER",
    "DATABASE.PASSWORD",
    "DATABASE.URL",
    "REDIS.HOST",
    "REDIS.PORT",
    "REDIS.URL",
    "CACHE.TTL",
    "CACHE.BACKEND",
    "API.KEY",
    "API.SECRET",
    "API.BASE_URL",
    "WORKER.CONCURRENCY",
    "WORKER.TIMEOUT",
    "SCHEDULER.INTERVAL",
    "LOGGING.LEVEL",
    "LOGGING.FORMAT",
    "LOGGING.OUTPUT",
    "STORAGE.BACKEND",
    "STORAGE.PATH",
    "STORAGE.BUCKET",
    "FEATURE.ENABLED",
    "SECURITY.SECRET_KEY",
    "SECURITY.ALGORITHM",
})


class Config:
    def __init__(self, config_path: Optional[str] = None):
        self._data: Dict[str, Any] = {}
        if config_path:
            self.load(config_path)
        self._load_env_overrides()

    def load(self, path: str) -> None:
        ext = os.path.splitext(path)[1].lower()
        with open(path) as f:
            if ext in (".yaml", ".yml"):
                import yaml
                self._data = yaml.safe_load(f) or {}
            else:
                self._data = json.load(f)

    def _load_env_overrides(self, allowed_keys: Optional[Set[str]] = None) -> None:
        prefix = "AO_"
        keys_to_check = allowed_keys if allowed_keys is not None else ALLOWED_CONFIG_KEYS
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].upper().replace("_", ".")
                # Only import if the key is in the allowlist
                if config_key in keys_to_check:
                    self._set_nested(config_key.lower(), value)

    def _set_nested(self, key: str, value: Any) -> None:
        parts = key.split(".")
        current = self._data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        current = self._data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return default
            else:
                return default
        return current

    def set(self, key: str, value: Any) -> None:
        self._set_nested(key, value)

    def to_dict(self) -> Dict:
        return self._data
