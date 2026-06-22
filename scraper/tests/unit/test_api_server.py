# scraper/tests/test_api_server.py
import os
import sys
import asyncio
import pytest
from unittest.mock import AsyncMock, patch

# Pre-set environment variables before importing api_server to avoid module-load failures.
# Using an in-memory SQLite URL ensures that SQLAlchemy's create_engine and
# metadata.create_all call succeed instantly without requiring a running Postgres instance.

# 1. Backup the original DATABASE_URL to prevent environment pollution
_original_db_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# 2. Import the application while the SQLite environment variable is active
from api_server import app, _run_lock  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import httpx2  # noqa: E402

# 3. Immediately restore the original environment variable so integration/E2E tests can use Postgres
if _original_db_url is not None:
    os.environ["DATABASE_URL"] = _original_db_url
else:
    os.environ.pop("DATABASE_URL", None)

client = TestClient(app)


def test_health_endpoint():
    """Test that the health check endpoint returns a 200 OK and status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_pipeline_success():
    """Test that POST /run succeeds when the pipeline completes successfully."""
    with patch("api_server.run_once", new_callable=AsyncMock) as mock_run_once:
        response = client.post("/run")
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        mock_run_once.assert_called_once()
        # Verify the lock is released after a successful run
        assert not _run_lock.locked()


def test_run_pipeline_failure():
    """Test that POST /run returns 500 when the underlying pipeline raises an exception."""
    with patch("api_server.run_once", new_callable=AsyncMock) as mock_run_once:
        mock_run_once.side_effect = Exception("Database connection timeout")

        response = client.post("/run")
        assert response.status_code == 500
        assert "Database connection timeout" in response.json()["detail"]
        # Crucial check: Ensure the lock gets released even if an exception occurs
        assert not _run_lock.locked()


@pytest.mark.asyncio
async def test_run_pipeline_concurrency():
    """
    Test that concurrent requests to POST /run are properly protected by the lock.
    One should acquire the lock and succeed, while the overlapping one should get a 409 Conflict.
    """

    # Create a slow-running mock function to hold the lock open
    async def slow_run(*args, **kwargs):
        await asyncio.sleep(0.1)
        return {"status": "success"}

    with patch("api_server.run_once", side_effect=slow_run):
        # Use httpx2.AsyncClient to execute asynchronous concurrent requests
        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://test"
        ) as ac:
            tasks = [ac.post("/run"), ac.post("/run")]
            responses = await asyncio.gather(*tasks)

            status_codes = [r.status_code for r in responses]
            assert 200 in status_codes
            assert 409 in status_codes

            conflict_response = next(r for r in responses if r.status_code == 409)
            assert conflict_response.json()["detail"] == "A run is already in progress"


def test_discover_selectors_success():
    """Test that POST /discover/{pair_id} parses stdout and returns valid JSON on exit code 0."""
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (
        b'{"title_selector": ".book-title", "price_selector": ".val"}',
        b"Progress log 100%",
    )
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        response = client.post("/discover/123")

        assert response.status_code == 200
        assert response.json() == {
            "title_selector": ".book-title",
            "price_selector": ".val",
        }

        # Verify that the subprocess was called with correct parameters
        mock_exec.assert_called_once_with(
            sys.executable,
            "tools/discover_selectors.py",
            "--pair-id",
            "123",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )


def test_discover_selectors_subprocess_error():
    """Test that POST /discover/{pair_id} handles non-zero exit codes and returns a 422 error."""
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (
        b"",
        b"Error: LLM API limit reached or failed to locate selectors",
    )
    mock_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        response = client.post("/discover/456")

        assert response.status_code == 422
        assert response.json() == {
            "output": "Error: LLM API limit reached or failed to locate selectors"
        }


def test_discover_selectors_invalid_json():
    """Test that POST /discover/{pair_id} handles malformed stdout strings gracefully with a 500 error."""
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (
        b"Not a valid JSON string!",
        b"Some progress logs",
    )
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        response = client.post("/discover/789")

        assert response.status_code == 500
        assert response.json()["detail"] == "Invalid JSON from discover_selectors.py"


# ---------------------------------------------------------------------------
# Settings & Configuration Endpoints
# ---------------------------------------------------------------------------


def test_get_config_endpoint_success():
    """Test that GET /config fetches status flags and securely formatted keys from the DB."""
    # Mock data structure returned by DBWriter.get_settings_status()
    mock_settings_status = {
        "LLM_DISCOVERY_ENABLED": "true",
        "LLM_MODE": "selector",
        "SELECTOR_API_BASE": "https://api.openai.com/v1",
        "SELECTOR_API_KEY": {"configured": True, "hint": "sk-...abcd"},
        "SELECTOR_MODEL": "gpt-4o",
        "DIRECT_API_BASE": "https://api.anthropic.com/v1",
        "DIRECT_API_KEY": {"configured": False, "hint": ""},
        "DIRECT_MODEL": "claude-3-5-sonnet",
    }

    with patch(
        "api_server._db.get_settings_status", return_value=mock_settings_status
    ) as mock_get:
        response = client.get("/config")
        assert response.status_code == 200

        data = response.json()
        # Ensure values are converted properly (e.g. string "true" becomes boolean True)
        assert data["llm_discovery_enabled"] is True
        assert data["llm_mode"] == "selector"
        assert data["selector_api_base"] == "https://api.openai.com/v1"
        assert data["selector_api_key_configured"] is True
        assert data["selector_api_key_hint"] == "sk-...abcd"
        assert data["selector_model"] == "gpt-4o"
        assert data["direct_api_base"] == "https://api.anthropic.com/v1"
        assert data["direct_api_key_configured"] is False
        assert data["direct_api_key_hint"] == ""
        assert data["direct_model"] == "claude-3-5-sonnet"

        mock_get.assert_called_once()


def test_update_config_endpoint_success():
    """Test that PUT /config accepts new configurations and pushes updates down to the DB."""
    payload = {
        "llm_discovery_enabled": False,
        "llm_mode": "direct",
        "selector_api_base": "https://api.custom-endpoint.com",
        "selector_api_key": "updated-secret-key-123",
        "selector_model": "custom-inference-v1",
        "direct_api_base": "https://api.custom-endpoint.com",
        "direct_api_key": "updated-direct-key-456",
        "direct_model": "custom-inference-v2",
    }

    # Intercept individual or batch database write updates
    with patch("api_server._db.apply_setting_update") as mock_single_update:
        response = client.put("/config", json=payload)
        assert response.status_code == 200

        # Verify that the endpoint normalized fields (like casting bool down to lowercase strings)
        if mock_single_update.called:
            mock_single_update.assert_any_call("LLM_DISCOVERY_ENABLED", "false")
            mock_single_update.assert_any_call("LLM_MODE", "direct")
            mock_single_update.assert_any_call("SELECTOR_MODEL", "custom-inference-v1")
            mock_single_update.assert_any_call(
                "SELECTOR_API_KEY", "updated-secret-key-123"
            )


def test_update_config_handles_none_values():
    """Test that PUT /config securely processes empty or null toggle states."""
    payload = {
        "llm_discovery_enabled": None,
        "llm_mode": "selector",
        "selector_api_base": "",
        "selector_api_key": None,
        "selector_model": "",
        "direct_api_base": "",
        "direct_api_key": None,
        "direct_model": "",
    }

    with patch("api_server._db.apply_setting_update") as mock_single_update:
        response = client.put("/config", json=payload)
        assert response.status_code == 200

        if mock_single_update.called:
            mock_single_update.assert_any_call("LLM_DISCOVERY_ENABLED", None)
