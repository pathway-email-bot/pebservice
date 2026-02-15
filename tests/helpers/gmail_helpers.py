"""
Shared helper: Gmail API utilities for integration tests.

Provides helpers to build Gmail credentials, send test emails,
and poll for emails (used by grading flow tests).

Usage:
    from tests.helpers.gmail_helpers import get_test_gmail_service, send_email
"""

import base64
import json
import os
import time
from email.mime.text import MIMEText

PROJECT_ID = "pathway-email-bot-6543"


def _get_secret(name: str) -> str:
    """Read a secret from Secret Manager."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    full_name = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
    response = client.access_secret_version(request={"name": full_name})
    return response.payload.data.decode("UTF-8").strip()


def _read_local_file(path: str) -> dict | None:
    """Read a JSON file relative to the repo root."""
    repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
    full = os.path.join(repo_root, path)
    if os.path.exists(full):
        with open(full) as f:
            return json.load(f)
    return None


def get_test_gmail_service():
    """
    Get Gmail API service for the TEST account (michaeltreynolds.test@gmail.com).

    Tries local files first, then falls back to Secret Manager (CI).
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    # Local files (developer machine)
    cfg_data = _read_local_file("client_config.secret.json")
    tok_data = _read_local_file("token.test.secret.json")

    if cfg_data and tok_data:
        cfg = cfg_data.get("installed") or cfg_data.get("web")
        creds = Credentials(
            None,
            refresh_token=tok_data["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
        )
    else:
        # Fall back to Secret Manager (CI)
        creds = Credentials(
            None,
            refresh_token=_get_secret("gmail-refresh-token-test"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=_get_secret("gmail-client-id"),
            client_secret=_get_secret("gmail-client-secret"),
        )

    return build("gmail", "v1", credentials=creds)


def send_email(gmail_service, *, from_email: str, to_email: str, subject: str, body: str) -> str:
    """
    Send an email via Gmail API and return the message ID.
    """
    msg = MIMEText(body)
    msg["to"] = to_email
    msg["from"] = from_email
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    sent = gmail_service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    assert "id" in sent, f"Gmail send failed: {sent}"
    return sent["id"]


def poll_firestore_for_grading(db, email: str, attempt_id: str, timeout: int = 120, interval: int = 5) -> dict:
    """
    Poll a Firestore attempt document until it reaches 'graded' status.

    Returns the attempt data dict, or raises AssertionError on timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        doc = (
            db.collection("users")
            .document(email)
            .collection("attempts")
            .document(attempt_id)
            .get()
        )
        data = doc.to_dict()
        if data and (data.get("score") is not None or data.get("status") == "graded"):
            return data
        time.sleep(interval)

    raise AssertionError(
        f"Timed out after {timeout}s waiting for grading — "
        f"last status was '{data.get('status') if data else 'no data'}'"
    )
