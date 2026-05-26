"""Tests for API Gateway Foundation."""
import pytest
from fastapi.testclient import TestClient

from mdpilot.api.routers.frontend import _llm_chat_completions_url


TEST_BEARER_TOKEN = "test-token"


@pytest.fixture
def accept_synthetic_auth_token(monkeypatch):
    """Make auth-gated endpoint tests independent of real API_TOKEN settings."""
    from mdpilot.config.settings import Settings
    import mdpilot.config.settings as settings_module

    monkeypatch.setattr(settings_module, "_settings", Settings(api_token=None))


def test_create_app():
    """Test that the app can be created."""
    from mdpilot.api.app import create_app

    app = create_app()
    assert app is not None
    assert app.app.title == "MDPilot API"


def test_health_check():
    """Test health check endpoint."""
    from mdpilot.api.app import create_app

    app = create_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_version_endpoint():
    """Test version endpoint."""
    from mdpilot.api.app import create_app

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/v1/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "api_version" in data
    assert data["api_version"] == "v1"


def test_cors_enabled():
    """Test that CORS is enabled."""
    from mdpilot.api.app import create_app

    app = create_app()
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_chats_preflight_allows_frontend_authorization_headers():
    """Test that chat preflight requests include CORS headers."""
    from mdpilot.api.app import create_app

    app = create_app()
    client = TestClient(app)

    response = client.options(
        "/api/chats",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_chats_error_response_keeps_cors_header_for_browser_visibility(accept_synthetic_auth_token):
    """Test that frontend chat errors are visible instead of masked as CORS failures."""
    from mdpilot.api.app import create_app

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(
        "/api/chats",
        headers={
            "Origin": "http://localhost:5173",
            "Authorization": f"Bearer {TEST_BEARER_TOKEN}",
        },
    )
    assert response.status_code == 500
    assert "access-control-allow-origin" in response.headers


def test_chats_default_client_reraises_server_exception(accept_synthetic_auth_token):
    """Test that uninitialized chat DB failures are not masked by middleware."""
    from mdpilot.api.app import create_app

    app = create_app()
    client = TestClient(app)

    with pytest.raises(Exception):
        client.get(
            "/api/chats",
            headers={
                "Origin": "http://localhost:5173",
                "Authorization": f"Bearer {TEST_BEARER_TOKEN}",
            },
        )


def test_config_loading():
    """Test that config can be loaded."""
    from mdpilot.api.config import Settings

    settings = Settings()
    assert settings.app_name == "MDPilot API"
    assert settings.api_version == "v1"
    assert settings.debug is False


def test_llm_chat_completions_url_accepts_base_or_v1_endpoint():
    assert _llm_chat_completions_url("https://api.example.com") == "https://api.example.com/v1/chat/completions"
    assert _llm_chat_completions_url("https://api.example.com/v1") == "https://api.example.com/v1/chat/completions"
    assert _llm_chat_completions_url("https://api.example.com/v1/") == "https://api.example.com/v1/chat/completions"
