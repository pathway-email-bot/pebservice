"""
Local test: start_scenario() function called directly.

Imports the start_scenario function and calls it with a mock Flask
request but against REAL GCP services (Firestore, Gmail, Secret Manager).
Tests auth validation, attempt creation, and starter email sending
without needing the function to be deployed.

Run:  python -m pytest tests/local/test_start_scenario.py -v --timeout=60
"""

from unittest.mock import MagicMock

import pytest

PROJECT_ID = "pathway-email-bot-6543"
TEST_EMAIL = "michaeltreynolds.test@gmail.com"
SCENARIO_ID = "missed_remote_standup"


# ── Helpers ──────────────────────────────────────────────────────────


def _call_start_scenario(*, body: dict = None, token: str = None, method: str = "POST"):
    """Call the /start_scenario endpoint via the Flask test client."""
    from service.main import app
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    with app.test_client() as client:
        if method == "OPTIONS":
            resp = client.options("/start_scenario", headers=headers)
            return resp.get_data(), resp.status_code, resp.headers
        else:
            resp = client.post("/start_scenario", json=body or {}, headers=headers)
            return resp.get_json() if resp.is_json else resp.get_data(), resp.status_code, resp.headers


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def id_token():
    """Get a real Firebase ID token for the test user."""
    from tests.helpers.firebase_auth import get_test_id_token
    return get_test_id_token(TEST_EMAIL)


@pytest.fixture(scope="module")
def db():
    """Firestore client for the 'pathway' database."""
    from tests.helpers.firestore_helpers import get_firestore_db
    return get_firestore_db()


@pytest.fixture(autouse=True)
def _hold_test_account_lock(db):
    """Hold the test-account mutex for the duration of each test."""
    from tests.helpers.firestore_helpers import test_user_lock
    with test_user_lock(db):
        yield  # lock held during entire test


# ── Tests ────────────────────────────────────────────────────────────


class TestStartScenarioLocal:
    """Call start_scenario() directly with mock requests, real services."""

    def test_successful_scenario_start(self, id_token, db):
        """Valid request creates a Firestore attempt and returns success."""
        response, status, headers = _call_start_scenario(
            body={"email": TEST_EMAIL, "scenarioId": SCENARIO_ID},
            token=id_token,
        )

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
        response, status, headers = _call_start_scenario(
            body={"email": TEST_EMAIL, "scenarioId": SCENARIO_ID},
        )
        assert status == 401

    def test_invalid_scenario_returns_404(self, id_token):
        """Request with nonexistent scenario returns 404."""
        response, status, headers = _call_start_scenario(
            body={"email": TEST_EMAIL, "scenarioId": "totally_fake_scenario"},
            token=id_token,
        )
        assert status == 404

    def test_email_mismatch_returns_403(self, id_token):
        """Request where email doesn't match token returns 403."""
        response, status, headers = _call_start_scenario(
            body={"email": "impersonator@evil.com", "scenarioId": SCENARIO_ID},
            token=id_token,
        )
        assert status == 403

    def test_cors_preflight_returns_204(self):
        """OPTIONS request returns 204 with CORS headers."""
        data, status, headers = _call_start_scenario(method="OPTIONS")
        assert status == 204
        assert "Access-Control-Allow-Origin" in headers
