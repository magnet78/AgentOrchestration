"""Tests for the OrchestratorClient SDK."""

import os
import pytest
from src.sdk.client import OrchestratorClient, MissingAPIKeyError


class TestOrchestratorClientInit:
    """Test client initialization and API key validation."""

    def test_missing_api_key_raises_on_request(self):
        """Test that missing API key raises MissingAPIKeyError."""
        # Clear env vars to simulate missing key
        old_key = os.environ.pop("AO_API_KEY", None)
        try:
            client = OrchestratorClient(api_key="")
            with pytest.raises(MissingAPIKeyError, match="No API key provided"):
                client._request("GET", "/agents")
        finally:
            if old_key is not None:
                os.environ["AO_API_KEY"] = old_key

    def test_none_api_key_raises_on_request(self):
        """Test that None API key raises MissingAPIKeyError."""
        old_key = os.environ.pop("AO_API_KEY", None)
        try:
            client = OrchestratorClient(api_key=None)
            with pytest.raises(MissingAPIKeyError, match="No API key provided"):
                client._request("GET", "/agents")
        finally:
            if old_key is not None:
                os.environ["AO_API_KEY"] = old_key

    def test_env_var_api_key_used(self):
        """Test that AO_API_KEY env var is used when no api_key arg is passed."""
        os.environ["AO_API_KEY"] = "test-env-key"
        try:
            client = OrchestratorClient()
            assert client.api_key == "test-env-key"
        finally:
            os.environ.pop("AO_API_KEY", None)

    def test_explicit_api_key_overrides_env(self):
        """Test that explicit api_key argument overrides env var."""
        os.environ["AO_API_KEY"] = "env-key"
        try:
            client = OrchestratorClient(api_key="explicit-key")
            assert client.api_key == "explicit-key"
        finally:
            os.environ.pop("AO_API_KEY", None)

    def test_api_key_validation_passes_with_key(self):
        """Test that _validate_api_key passes when key is set."""
        client = OrchestratorClient(api_key="valid-key")
        # Should not raise
        client._validate_api_key()

    def test_default_base_url(self):
        """Test default base URL."""
        client = OrchestratorClient(api_key="test")
        assert client.base_url == "https://api.agent-orchestrator.io"

    def test_custom_base_url(self):
        """Test custom base URL."""
        client = OrchestratorClient(base_url="https://custom.example.com", api_key="test")
        assert client.base_url == "https://custom.example.com"
