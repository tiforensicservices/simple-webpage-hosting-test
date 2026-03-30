"""tests/test_api.py — Unit tests for the FastAPI application.

Tests cover:
  - Health check endpoint
  - Config status endpoint
  - Version endpoint
  - Echo endpoint
  - Error handling
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config import get_config


@pytest.fixture
def client():
    """Fixture to provide a FastAPI test client."""
    return TestClient(app)


class TestHealthCheck:
    """Tests for GET /health endpoint."""

    def test_health_check_returns_ok(self, client):
        """Health check should return 200 with status 'ok'."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "api_configured" in data

    def test_health_check_response_structure(self, client):
        """Health check response must include all required fields."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["status"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["api_configured"], bool)


class TestConfigStatus:
    """Tests for GET /config-status endpoint."""

    def test_config_status_returns_ok(self, client):
        """Config status should return 200."""
        response = client.get("/config-status")
        assert response.status_code == 200

    def test_config_status_response_structure(self, client):
        """Config status response must include all required fields."""
        response = client.get("/config-status")
        data = response.json()
        assert "api_key_configured" in data
        assert "aws_region" in data
        assert "s3_bucket_configured" in data
        assert "message" in data
        assert isinstance(data["api_key_configured"], bool)
        assert isinstance(data["s3_bucket_configured"], bool)

    def test_config_status_message_reflects_state(self, client):
        """Config status message should accurately reflect configuration state."""
        response = client.get("/config-status")
        data = response.json()
        # Message should indicate either "All configured" or list missing items
        assert (
            "All configured" in data["message"]
            or "Missing:" in data["message"]
        )


class TestVersion:
    """Tests for GET /version endpoint."""

    def test_version_returns_ok(self, client):
        """Version endpoint should return 200."""
        response = client.get("/version")
        assert response.status_code == 200

    def test_version_response_structure(self, client):
        """Version response must include version and name."""
        response = client.get("/version")
        data = response.json()
        assert "version" in data
        assert "name" in data
        assert data["version"] == "0.1.0"
        assert "Gaitway" in data["name"]


class TestRoot:
    """Tests for GET / endpoint."""

    def test_root_returns_ok(self, client):
        """Root endpoint should return 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_structure(self, client):
        """Root response must include message, version, and endpoints."""
        response = client.get("/")
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data
        assert data["version"] == "0.1.0"

    def test_root_lists_key_endpoints(self, client):
        """Root response should list key endpoints."""
        response = client.get("/")
        data = response.json()
        endpoints = data["endpoints"]
        assert "health" in endpoints
        assert "config_status" in endpoints
        assert "version" in endpoints
        assert "docs" in endpoints


class TestEcho:
    """Tests for POST /echo endpoint."""

    def test_echo_returns_ok(self, client):
        """Echo endpoint should return 200."""
        payload = {"test": "data"}
        response = client.post("/echo", json=payload)
        assert response.status_code == 200

    def test_echo_reflects_input(self, client):
        """Echo endpoint should return the input data."""
        payload = {"message": "hello", "value": 42}
        response = client.post("/echo", json=payload)
        data = response.json()
        assert data["received"] == payload

    def test_echo_includes_timestamp(self, client):
        """Echo endpoint should include a timestamp."""
        payload = {"test": "data"}
        response = client.post("/echo", json=payload)
        data = response.json()
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # ISO format includes 'T'

    def test_echo_includes_api_version(self, client):
        """Echo endpoint should include API version in response."""
        response = client.post("/echo", json={})
        data = response.json()
        assert "api_version" in data
        assert data["api_version"] == "0.1.0"

    def test_echo_with_empty_payload(self, client):
        """Echo should handle empty JSON payload."""
        response = client.post("/echo", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["received"] == {}

    def test_echo_with_complex_payload(self, client):
        """Echo should handle nested and complex payloads."""
        payload = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "number": 42,
            "string": "test",
        }
        response = client.post("/echo", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["received"] == payload


class TestConfigIntegration:
    """Tests verifying API uses centralized config."""

    def test_config_loads_successfully(self):
        """Config should load without errors."""
        cfg = get_config()
        assert cfg is not None
        assert hasattr(cfg, "api_key")
        assert hasattr(cfg, "aws_region")
        assert hasattr(cfg, "s3_bucket")

    def test_api_reflects_config_state(self, client):
        """API endpoints should reflect actual config state."""
        cfg = get_config()
        response = client.get("/config-status")
        data = response.json()
        # Verify config is reflected in endpoint
        assert data["api_key_configured"] == bool(cfg.api_key)
        assert data["s3_bucket_configured"] == bool(cfg.s3_bucket)


class TestErrorHandling:
    """Tests for error handling."""

    def test_undefined_route_returns_404(self, client):
        """Accessing undefined route should return 404."""
        response = client.get("/undefined-route")
        assert response.status_code == 404

    def test_method_not_allowed_returns_405(self, client):
        """Using wrong HTTP method should return 405."""
        response = client.put("/health")
        assert response.status_code == 405

    def test_echo_without_json_returns_422(self, client):
        """Posting to echo without JSON should fail validation."""
        # Use content= (bytes) to avoid httpx DeprecationWarning for data=
        response = client.post("/echo", content=b"not json", headers={"content-type": "text/plain"})
        # FastAPI returns 422 (Unprocessable Entity) for validation errors
        assert response.status_code in [400, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
