"""Tests for ETag-based optimistic concurrency control on agent config."""

import pytest
from src.agent.registry import AgentRegistry
from fastapi.testclient import TestClient
from src.api.routes import router


def test_etag_computation_is_deterministic():
    """Same config should produce the same ETag."""
    config = {"key": "value", "nested": {"a": 1}}
    etag1 = AgentRegistry._compute_etag(config)
    etag2 = AgentRegistry._compute_etag(config)
    assert etag1 == etag2
    assert etag1.startswith('W/"')
    assert etag1.endswith('"')


def test_etag_changes_on_config_change():
    """Different configs should produce different ETags."""
    config1 = {"key": "value"}
    config2 = {"key": "different"}
    etag1 = AgentRegistry._compute_etag(config1)
    etag2 = AgentRegistry._compute_etag(config2)
    assert etag1 != etag2


def test_update_config_without_etag_succeeds():
    """Update without ETag should always succeed (backward compat)."""
    registry = AgentRegistry()
    agent_id = registry.register("test-agent", "worker")
    result = registry.update_config(agent_id, {"setting": "new_value"})
    assert result is not None
    assert result["config"]["setting"] == "new_value"


def test_update_config_with_matching_etag_succeeds():
    """Update with matching ETag should succeed."""
    registry = AgentRegistry()
    agent_id = registry.register("test-agent", "worker", config={"initial": True})
    agent = registry.get(agent_id)
    etag = registry._compute_etag(agent["config"])

    result = registry.update_config(agent_id, {"added": True}, if_match=etag)
    assert result is not None
    assert result["config"]["initial"] is True
    assert result["config"]["added"] is True


def test_update_config_with_stale_etag_fails():
    """Update with stale ETag should return None (412 equivalent)."""
    registry = AgentRegistry()
    agent_id = registry.register("test-agent", "worker", config={"v": 1})

    # Get the ETag
    agent = registry.get(agent_id)
    stale_etag = registry._compute_etag(agent["config"])

    # Modify the config (simulating another client update)
    registry.update_config(agent_id, {"v": 2})

    # Try to update with the stale ETag
    result = registry.update_config(agent_id, {"v": 3}, if_match=stale_etag)
    assert result is None  # Rejected due to stale ETag


def test_update_config_nonexistent_agent():
    """Update for non-existent agent should return None."""
    registry = AgentRegistry()
    result = registry.update_config("nonexistent", {"key": "val"})
    assert result is None


def test_update_config_nonexistent_with_etag():
    """Update for non-existent agent with ETag should return None."""
    registry = AgentRegistry()
    result = registry.update_config("nonexistent", {"key": "val"}, if_match='W/"abc"')
    assert result is None
