"""
End-to-end integration test: full grading pipeline.

Creates a Firestore attempt → sends a real email to the bot → polls Firestore
until the attempt is graded. Verifies score, feedback, and status.

Credentials:
  - Locally: reads from client_config.secret.json + token.test.secret.json
  - In CI: reads from Secret Manager (gmail-client-config, gmail-test-token)

Run:  python -m pytest tests/integration/test_e2e_grading.py -v --timeout=180
Cost: ~$0.01 per run (1 OpenAI API call)
"""

import base64
import json
import os
import time
import uuid

import pytest

PROJECT_ID = "pathway-email-bot-6543"
TEST_EMAIL = "michaeltreynolds.test@gmail.com"
BOT_EMAIL = "pathwayemailbot@gmail.com"
SCENARIO_ID = "missed_remote_standup"
POLL_INTERVAL = 5
POLL_TIMEOUT = 120


# ── Helpers ──────────────────────────────────────────────────────────


def _get_secret(name: str) -> str:
    """Read a secret from Secret Manager."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    full_name = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
    response = client.access_secret_version(request={"name": full_name})
    return response.payload.data.decode("UTF-8").strip()


def _read_local_file(path: str) -> dict:
    """Read a JSON file relative to the repo root."""
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    full = os.path.join(repo_root, path)
    if os.path.exists(full):
        with open(full) as f:
            return json.load(f)
    return None


def _get_gmail_credentials():
    """Get Gmail OAuth credentials — try local files first, then Secret Manager."""
    from google.oauth2.credentials import Credentials

    # Local files (developer machine)
    cfg_data = _read_local_file("client_config.secret.json")
    tok_data = _read_local_file("token.test.secret.json")

    if cfg_data and tok_data:
        cfg = cfg_data.get("installed") or cfg_data.get("web")
        return Credentials(
            None,
            refresh_token=tok_data["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
        )

    # Fall back to individual secrets from Secret Manager (CI)
    return Credentials(
        None,
        refresh_token=_get_secret("gmail-refresh-token-test"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_get_secret("gmail-client-id"),
        client_secret=_get_secret("gmail-client-secret"),
    )


# ── Fixtures ─────────────────────────────────────────────────────────


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


@pytest.fixture(scope="module")
def gmail():
    """Authenticated Gmail API service for the test account."""
    from googleapiclient.discovery import build

    creds = _get_gmail_credentials()
    return build("gmail", "v1", credentials=creds)


# ── Test ─────────────────────────────────────────────────────────────


class TestEndToEndGrading:
    """Full E2E: create attempt → send email → poll for grading."""

    def test_email_grading_pipeline(self, db, gmail):
        from firebase_admin import firestore as fb_firestore
        from email.mime.text import MIMEText

        # --- Step 1: Create Firestore attempt ---
        attempt_ref = (
            db.collection("users")
            .document(TEST_EMAIL)
            .collection("attempts")
            .document()
        )
        attempt_ref.set({
            "scenarioId": SCENARIO_ID,
            "status": "pending",
            "createdAt": fb_firestore.SERVER_TIMESTAMP,
            "startedAt": fb_firestore.SERVER_TIMESTAMP,
        })

        user_ref = db.collection("users").document(TEST_EMAIL)
        user_ref.set({
            "activeScenarioId": SCENARIO_ID,
            "activeAttemptId": attempt_ref.id,
        }, merge=True)

        # --- Step 2: Send test email ---
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

        subject = f"Re: Missed Remote Standup - {SCENARIO_ID} [test-{tag}]"
        msg = MIMEText(body_text)
        msg["to"] = BOT_EMAIL
        msg["from"] = TEST_EMAIL
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        sent = gmail.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        assert "id" in sent, f"Gmail send failed: {sent}"

        # --- Step 3: Poll Firestore for grading ---
        start = time.time()
        final_data = None
        while time.time() - start < POLL_TIMEOUT:
            doc = attempt_ref.get()
            data = doc.to_dict()
            status = data.get("status")
            score = data.get("score")

            if score is not None or status == "graded":
                final_data = data
                break

            time.sleep(POLL_INTERVAL)

        # --- Assertions ---
        assert final_data is not None, (
            f"Timed out after {POLL_TIMEOUT}s — status was '{data.get('status')}'"
        )
        assert final_data["status"] == "graded"
        assert isinstance(final_data["score"], (int, float))
        assert final_data["score"] >= 0
        assert "feedback" in final_data
        assert len(final_data["feedback"]) > 10, "Feedback should be substantive"
