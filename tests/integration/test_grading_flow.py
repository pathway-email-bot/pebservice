"""
Integration test: full grading flow via deployed services.

Clean version of the E2E grading test that uses the start_scenario
endpoint (no direct Firestore manipulation for setup):
  1. POST /start_scenario → creates attempt
  2. Send email to bot via Gmail API
  3. Poll Firestore for grading result

Run:  python -m pytest tests/integration/test_grading_flow.py -v --timeout=180
Cost: ~$0.01 per run (1 OpenAI API call via the deployed function)
"""

import os
import uuid

import pytest

PROJECT_ID = "pathway-email-bot-6543"
REGION = "us-central1"
START_SCENARIO_URL = f"https://{REGION}-{PROJECT_ID}.cloudfunctions.net/start_scenario"
TEST_EMAIL = "michaeltreynolds.test@gmail.com"
BOT_EMAIL = "pathwayemailbot@gmail.com"
SCENARIO_ID = "missed_remote_standup"
POLL_TIMEOUT = 120
POLL_INTERVAL = 5


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def id_token():
    """Firebase ID token for the test user."""
    from tests.helpers.firebase_auth import get_test_id_token
    return get_test_id_token(TEST_EMAIL)


@pytest.fixture(scope="module")
def gmail():
    """Authenticated Gmail service for the test account."""
    from tests.helpers.gmail_helpers import get_test_gmail_service
    return get_test_gmail_service()


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


# ── Test ─────────────────────────────────────────────────────────────


class TestGradingFlow:
    """Full E2E: start_scenario API → send email → poll for grading."""

    def test_scenario_to_grade(self, id_token, gmail, db):
        import requests as http_requests
        from tests.helpers.gmail_helpers import send_email, poll_firestore_for_grading

        # --- Step 1: Start scenario via deployed endpoint ---
        resp = http_requests.post(
            START_SCENARIO_URL,
            json={"email": TEST_EMAIL, "scenarioId": SCENARIO_ID},
            headers={"Authorization": f"Bearer {id_token}"},
        )
        assert resp.status_code == 200, f"start_scenario failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["success"] is True
        attempt_id = data["attemptId"]

        # --- Step 2: Send test email to bot ---
        tag = uuid.uuid4().hex[:6]
        body_text = (
            "Hi team,\n\n"
            "I apologize for missing the standup this morning. I overslept due "
            "to a late night debugging a production issue.\n\n"
            "Yesterday: Completed the API endpoint refactoring.\n"
            "Today: Planning to finish the database migration script.\n"
            "Blockers: Need staging database credentials.\n\n"
            "Sorry for the inconvenience.\n\n"
            "Best regards"
        )

        send_email(
            gmail,
            from_email=TEST_EMAIL,
            to_email=BOT_EMAIL,
            subject=f"Re: Missed Remote Standup - {SCENARIO_ID} [test-{tag}]",
            body=body_text,
        )

        # --- Step 3: Poll Firestore for grading ---
        final_data = poll_firestore_for_grading(
            db, TEST_EMAIL, attempt_id,
            timeout=POLL_TIMEOUT, interval=POLL_INTERVAL,
        )

        # --- Assertions ---
        assert final_data["status"] == "graded"
        assert isinstance(final_data["score"], (int, float))
        assert final_data["score"] >= 0
        assert "feedback" in final_data
        assert len(final_data["feedback"]) > 10, "Feedback should be substantive"
