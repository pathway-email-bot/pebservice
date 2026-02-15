"""
Integration test: start_scenario HTTP endpoint.

POSTs to the DEPLOYED start_scenario Cloud Function with a real Firebase
ID token and verifies:
  - Successful response with attemptId
  - Firestore attempt document was created
  - Error cases: missing auth, invalid scenario, email mismatch

Run:  python -m pytest tests/integration/test_start_scenario_api.py -v --timeout=60
"""

import os
import pytest
import requests as http_requests

PROJECT_ID = "pathway-email-bot-6543"
REGION = "us-central1"
START_SCENARIO_URL = f"https://{REGION}-{PROJECT_ID}.cloudfunctions.net/start_scenario"
TEST_EMAIL = "michaeltreynolds.test@gmail.com"
SCENARIO_ID = "missed_remote_standup"


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def id_token():
    """Get a Firebase ID token for the test user."""
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


class TestStartScenarioAPI:
    """Test the deployed start_scenario HTTP endpoint."""

    def test_start_scenario_success(self, id_token, db):
        """POST with valid token and scenarioId returns success + creates Firestore attempt."""
        resp = http_requests.post(
            START_SCENARIO_URL,
            json={"email": TEST_EMAIL, "scenarioId": SCENARIO_ID},
            headers={"Authorization": f"Bearer {id_token}"},
        )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert "attemptId" in data

        # Verify Firestore has the attempt
        attempt_id = data["attemptId"]
        attempt_doc = (
            db.collection("users")
            .document(TEST_EMAIL)
            .collection("attempts")
            .document(attempt_id)
            .get()
        )
        assert attempt_doc.exists, f"Attempt {attempt_id} not found in Firestore"
        attempt_data = attempt_doc.to_dict()
        assert attempt_data["scenarioId"] == SCENARIO_ID
        assert attempt_data["status"] == "pending"

        # Cleanup: delete the test attempt
        attempt_doc.reference.delete()

    def test_missing_auth_returns_401(self):
        """POST without Authorization header returns 401."""
        resp = http_requests.post(
            START_SCENARIO_URL,
            json={"email": TEST_EMAIL, "scenarioId": SCENARIO_ID},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_invalid_scenario_returns_404(self, id_token):
        """POST with nonexistent scenarioId returns 404."""
        resp = http_requests.post(
            START_SCENARIO_URL,
            json={"email": TEST_EMAIL, "scenarioId": "nonexistent_scenario_xyz"},
            headers={"Authorization": f"Bearer {id_token}"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_email_mismatch_returns_403(self, id_token):
        """POST where email doesn't match token returns 403."""
        resp = http_requests.post(
            START_SCENARIO_URL,
            json={"email": "someone.else@example.com", "scenarioId": SCENARIO_ID},
            headers={"Authorization": f"Bearer {id_token}"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_missing_scenario_id_returns_400(self, id_token):
        """POST without scenarioId returns 400."""
        resp = http_requests.post(
            START_SCENARIO_URL,
            json={"email": TEST_EMAIL},
            headers={"Authorization": f"Bearer {id_token}"},
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"

    def test_cors_preflight(self):
        """OPTIONS request returns CORS headers."""
        resp = http_requests.options(START_SCENARIO_URL)
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}"
        assert "access-control-allow-origin" in {k.lower() for k in resp.headers}
