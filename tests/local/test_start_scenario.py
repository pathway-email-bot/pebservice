"""
Local test: start_scenario() function called directly.

Imports the start_scenario function and calls it with a mock Flask
request but against REAL GCP services (Firestore, Gmail, Secret Manager).
Tests auth validation, attempt creation, and starter email sending
without needing the function to be deployed.

Run:  python -m pytest tests/local/test_start_scenario.py -v --timeout=60
"""

import json
import os
from unittest.mock import MagicMock

import pytest

PROJECT_ID = "pathway-email-bot-6543"
TEST_EMAIL = "michaeltreynolds.test@gmail.com"
SCENARIO_ID = "missed_remote_standup"


# ── Helpers ──────────────────────────────────────────────────────────


def _make_request(*, body: dict = None, token: str = None, method: str = "POST") -> MagicMock:
    """Build a mock Flask Request with the given body and auth token."""
    request = MagicMock()
    request.method = method
    request.get_json.return_value = body or {}
    request.headers = {}
    if token:
        request.headers["Authorization"] = f"Bearer {token}"
    return request


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def id_token():
    """Get a real Firebase ID token for the test user."""
    from tests.helpers.firebase_auth import get_test_id_token
    return get_test_id_token(TEST_EMAIL)


@pytest.fixture(scope="module")
def db():
    """Firestore client for the 'pathway' database."""
    import firebase_admin
    from google.cloud import firestore

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", PROJECT_ID)
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": PROJECT_ID})

    return firestore.Client(database="pathway")


# ── Tests ────────────────────────────────────────────────────────────


class TestStartScenarioLocal:
    """Call start_scenario() directly with mock requests, real services."""

    def test_successful_scenario_start(self, id_token, db):
        """Valid request creates a Firestore attempt and returns success."""
        from service.main import start_scenario

        request = _make_request(
            body={"email": TEST_EMAIL, "scenarioId": SCENARIO_ID},
            token=id_token,
        )
        response, status, headers = start_scenario(request)

        assert status == 200, f"Expected 200, got {status}: {response}"
        assert response["success"] is True
        assert "attemptId" in response

        # Verify Firestore
        attempt_id = response["attemptId"]
        doc = (
            db.collection("users")
            .document(TEST_EMAIL)
            .collection("attempts")
            .document(attempt_id)
            .get()
        )
        assert doc.exists, f"Attempt {attempt_id} not in Firestore"
        assert doc.to_dict()["status"] == "pending"

        # Cleanup
        doc.reference.delete()

    def test_missing_token_returns_401(self):
        """Request without auth token returns 401."""
        from service.main import start_scenario

        request = _make_request(
            body={"email": TEST_EMAIL, "scenarioId": SCENARIO_ID},
        )
        response, status, headers = start_scenario(request)
        assert status == 401

    def test_invalid_scenario_returns_404(self, id_token):
        """Request with nonexistent scenario returns 404."""
        from service.main import start_scenario

        request = _make_request(
            body={"email": TEST_EMAIL, "scenarioId": "totally_fake_scenario"},
            token=id_token,
        )
        response, status, headers = start_scenario(request)
        assert status == 404

    def test_email_mismatch_returns_403(self, id_token):
        """Request where email doesn't match token returns 403."""
        from service.main import start_scenario

        request = _make_request(
            body={"email": "impersonator@evil.com", "scenarioId": SCENARIO_ID},
            token=id_token,
        )
        response, status, headers = start_scenario(request)
        assert status == 403

    def test_cors_preflight_returns_204(self):
        """OPTIONS request returns 204 with CORS headers."""
        from service.main import start_scenario

        request = _make_request(method="OPTIONS")
        result = start_scenario(request)
        # CORS preflight returns a tuple: ('', 204, headers)
        assert result[1] == 204
        assert "Access-Control-Allow-Origin" in result[2]
