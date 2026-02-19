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


def get_secret(name: str) -> str:
    """Read a secret from Secret Manager."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    full_name = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
    response = client.access_secret_version(request={"name": full_name})
    return response.payload.data.decode("UTF-8").strip()


def get_test_gmail_service():
    """
    Get Gmail API service for the TEST account (michaeltreynolds.test@gmail.com).

    Always reads credentials from Secret Manager (single source of truth).
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=get_secret("gmail-refresh-token-test"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=get_secret("gmail-client-id"),
        client_secret=get_secret("gmail-client-secret"),
    )

    return build("gmail", "v1", credentials=creds)


def get_bot_gmail_service():
    """
    Get Gmail API service for the BOT account (pathwayemailbot@gmail.com).

    Always reads credentials from Secret Manager (single source of truth).
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    refresh_token_raw = get_secret("gmail-refresh-token-bot")
    try:
        token_data = json.loads(refresh_token_raw)
        refresh_token = token_data["refresh_token"]
    except (json.JSONDecodeError, KeyError):
        refresh_token = refresh_token_raw

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=get_secret("gmail-client-id"),
        client_secret=get_secret("gmail-client-secret"),
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


BOT_EMAIL = "pathwayemailbot@gmail.com"


def find_bot_email(
    gmail_service,
    *,
    subject_contains: str,
    sent_after: float,
    timeout: int = 60,
    poll_interval: int = 3,
) -> dict:
    """
    Poll the test account's inbox for an email from the bot matching a subject substring.

    Returns the full Gmail API message dict.
    Raises TimeoutError if not found within timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        results = gmail_service.users().messages().list(
            userId="me",
            q=f'from:{BOT_EMAIL} subject:"{subject_contains}"',
            maxResults=5,
        ).execute()

        for msg_meta in results.get("messages", []):
            msg = gmail_service.users().messages().get(
                userId="me", id=msg_meta["id"], format="full",
            ).execute()

            # Only consider emails sent AFTER the trigger time
            email_epoch = int(msg.get("internalDate", "0")) / 1000
            if email_epoch < sent_after:
                continue

            return msg

        time.sleep(poll_interval)

    raise TimeoutError(
        f"No email from bot with subject containing '{subject_contains}' "
        f"found within {timeout}s."
    )


def send_reply_email(
    gmail_service,
    *,
    original_msg: dict,
    from_email: str,
    body: str,
) -> str:
    """
    Send a threaded reply to an email via Gmail API.

    Sets In-Reply-To, References, and threadId for proper threading.
    Returns the sent message ID.
    """
    headers = original_msg.get("payload", {}).get("headers", [])

    def _get_header(name: str, default: str = "") -> str:
        name_lower = name.lower()
        return next(
            (h["value"] for h in headers if h["name"].lower() == name_lower),
            default,
        )

    subject = _get_header("Subject", "No Subject")
    sender = _get_header("From", BOT_EMAIL)
    message_id = _get_header("Message-ID")
    thread_id = original_msg.get("threadId")

    reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"

    msg = MIMEText(body)
    msg["to"] = sender
    msg["from"] = from_email
    msg["subject"] = reply_subject
    if message_id:
        msg["In-Reply-To"] = message_id
        msg["References"] = message_id

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    send_body = {"raw": raw}
    if thread_id:
        send_body["threadId"] = thread_id

    sent = gmail_service.users().messages().send(
        userId="me", body=send_body,
    ).execute()
    assert "id" in sent, f"Gmail reply send failed: {sent}"
    return sent["id"]
