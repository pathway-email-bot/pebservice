"""
Gmail client utilities for the PEB Service.

Handles Gmail API authentication, sending emails, MIME message building,
distributed watch renewal, and robust email body extraction.
"""

import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.cloud import firestore as firestore_lib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .logging_utils import log_function
from .secrets import get_secret

logger = logging.getLogger(__name__)


# ============================================================================
# Gmail Service (OAuth)
# ============================================================================


@log_function
def get_gmail_service():
    """Build Gmail service using OAuth credentials from Secret Manager."""
    try:
        client_id = get_secret("gmail-client-id")
        client_secret = get_secret("gmail-client-secret")

        # Refresh token is stored as JSON with metadata by get_token.py
        refresh_token_raw = get_secret("gmail-refresh-token-bot")
        try:
            token_data = json.loads(refresh_token_raw)
            refresh_token = token_data["refresh_token"]
        except (json.JSONDecodeError, KeyError):
            # Fallback: treat as plain string (backwards compat)
            refresh_token = refresh_token_raw

        creds = Credentials(
            None,  # No access token initially
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )

        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error(f"Auth error: {e}", exc_info=True)
        return None


# ============================================================================
# Email Sending
# ============================================================================


@log_function
def send_reply(service, original_msg, reply_text):
    """Send a reply to an email via Gmail API.

    Uses Python's MIMEText to produce a standards-compliant message with
    Content-Type, MIME-Version, and From headers (critical for deliverability).
    """
    try:
        thread_id = original_msg["threadId"]
        headers = original_msg["payload"]["headers"]

        from .main import get_header  # avoid circular at module level

        subject = get_header(headers, "Subject", "No Subject")
        sender_email = get_header(headers, "From", "")

        # Get the Message-ID for proper threading
        message_id = get_header(headers, "Message-ID") or None

        logger.info(f"Constructing reply message for thread: {thread_id}")

        # Build a proper MIME message with all required headers
        message = MIMEText(reply_text, "plain")
        message["To"] = sender_email
        message["From"] = "Pathway Email Bot <pathwayemailbot@gmail.com>"
        message["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject

        if message_id:
            message["In-Reply-To"] = message_id
            message["References"] = message_id

        raw_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("utf-8")
        body = {"raw": raw_message, "threadId": thread_id}

        sent_msg = (
            service.users().messages().send(userId="me", body=body).execute()
        )
        logger.info(f"Reply SENT successfully. ID: {sent_msg.get('id')}")

    except Exception as e:
        logger.error(f"Error sending reply: {e}", exc_info=True)


@log_function
def build_mime_message(
    from_addr: str, from_name: str, to_addr: str, subject: str, body: str,
    html: str | None = None,
) -> str:
    """Build a MIME message and return as base64-encoded string for Gmail API.

    Args:
        html: Optional HTML version of the email. If provided, creates a
              multipart/alternative message with both plain text and HTML parts.
    """
    if html:
        message = MIMEMultipart("alternative")
        message.attach(MIMEText(body, "plain"))
        message.attach(MIMEText(html, "html"))
    else:
        message = MIMEText(body, "plain")

    message["To"] = to_addr
    message["From"] = f"{from_name} <{from_addr}>"
    message["Subject"] = subject
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


# ============================================================================
# Email Body Extraction (robust MIME parsing)
# ============================================================================


def extract_email_body(msg: dict) -> str:
    """Extract plain-text body from a Gmail API message.

    Uses Python's ``email`` library for robust MIME parsing that handles
    nested multipart structures (multipart/mixed containing
    multipart/alternative, etc.).

    Falls back to the simple single-part body approach if no multipart
    parts are present.
    """
    payload = msg.get("payload", {})

    # Try to reconstruct full MIME message from raw if available
    raw = msg.get("raw")
    if raw:
        raw_bytes = base64.urlsafe_b64decode(raw)
        email_msg = message_from_bytes(raw_bytes)
        return _extract_text_from_email(email_msg)

    # Otherwise parse the Gmail API payload structure
    parts = payload.get("parts", [])
    if not parts:
        # Single-part message — body is directly on payload
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8")
        return ""

    # Walk parts recursively for text/plain
    return _walk_parts(parts)


def _walk_parts(parts: list) -> str:
    """Recursively walk MIME parts to find text/plain content."""
    for part in parts:
        mime_type = part.get("mimeType", "")

        # Nested multipart — recurse into sub-parts
        if mime_type.startswith("multipart/"):
            sub_parts = part.get("parts", [])
            if sub_parts:
                result = _walk_parts(sub_parts)
                if result:
                    return result

        # Found plain text
        if mime_type == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8")

    return ""


def _extract_text_from_email(msg) -> str:
    """Extract text/plain from a parsed email.message.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset)
    return ""


# ============================================================================
# Gmail Watch Renewal (lazy, distributed-safe)
# ============================================================================

# Module-level cache: avoids Firestore reads within the same instance
_watch_expires_at: datetime | None = None

_WATCH_TOPIC = "projects/pathway-email-bot-6543/topics/email-notifications"
_WATCH_DOC_PATH = ("system", "watch_status")
_WATCH_RENEW_BUFFER = timedelta(hours=24)  # renew when <24h left
_WATCH_CLAIM_TIMEOUT = timedelta(seconds=60)  # stale claim threshold
_WATCH_DURATION = timedelta(days=7)  # Gmail watch expiry


def ensure_watch(gmail_service):
    """Renew Gmail push-notification watch if nearing expiry.

    Uses a two-phase approach to prevent thundering herd:
      1. Firestore transaction claims renewal (only one instance wins)
      2. Winner calls Gmail watch() API
      3. Winner writes 'completed' status back to Firestore
    If the winner crashes, the claim expires after 60s so others can retry.
    """
    global _watch_expires_at
    now = datetime.now(timezone.utc)

    # Fast path: in-memory cache says watch is still fresh
    if _watch_expires_at and _watch_expires_at > now + _WATCH_RENEW_BUFFER:
        return

    from .firestore_client import get_firestore_client

    db = get_firestore_client()
    doc_ref = db.collection(*_WATCH_DOC_PATH[:1]).document(_WATCH_DOC_PATH[1])

    # Phase 1: Try to claim renewal via transaction
    transaction = db.transaction()
    if not _try_claim_watch_renewal(transaction, doc_ref, now):
        # Another instance is handling it, or watch is still fresh
        snap = doc_ref.get()
        if snap.exists:
            data = snap.to_dict()
            exp = data.get("expires_at")
            if exp:
                _watch_expires_at = (
                    exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
                )
        return

    # Phase 2: We won the claim — call watch()
    try:
        gmail_service.users().watch(
            userId="me",
            body={"labelIds": ["INBOX"], "topicName": _WATCH_TOPIC},
        ).execute()
    except Exception as e:
        logger.warning(f"Gmail watch renewal failed: {e}", exc_info=True)
        return  # claim will expire in 60s, another instance can retry

    # Phase 3: Confirm success
    new_expires = now + _WATCH_DURATION
    doc_ref.update(
        {
            "status": "completed",
            "expires_at": new_expires,
            "completed_at": now,
        }
    )
    _watch_expires_at = new_expires
    logger.info(f"Gmail watch renewed — expires {new_expires.isoformat()}")


@firestore_lib.transactional
def _try_claim_watch_renewal(transaction, doc_ref, now: datetime) -> bool:
    """Transactional wrapper — reads doc, delegates to pure logic."""
    snapshot = doc_ref.get(transaction=transaction)
    data = snapshot.to_dict() if snapshot.exists else {}
    should_claim = check_and_claim_watch(data, now)
    if should_claim:
        transaction.set(
            doc_ref,
            {
                "status": "renewing",
                "claimed_at": now,
                "expires_at": data.get("expires_at"),  # preserve old value
            },
        )
    return should_claim


def check_and_claim_watch(data: dict, now: datetime) -> bool:
    """Pure decision logic: should this instance claim watch renewal?

    Returns True if renewal is needed, False to skip.
    Testable without Firestore mocks.
    """
    expires_at = data.get("expires_at")
    status = data.get("status")
    claimed_at = data.get("claimed_at")

    # Normalise timestamps to UTC-aware
    if expires_at and not getattr(expires_at, "tzinfo", None):
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if claimed_at and not getattr(claimed_at, "tzinfo", None):
        claimed_at = claimed_at.replace(tzinfo=timezone.utc)

    # Case 1: Watch is fresh and confirmed — skip
    if (
        status == "completed"
        and expires_at
        and expires_at > now + _WATCH_RENEW_BUFFER
    ):
        return False

    # Case 2: Another instance is currently renewing (<60s ago) — skip
    if (
        status == "renewing"
        and claimed_at
        and (now - claimed_at) < _WATCH_CLAIM_TIMEOUT
    ):
        return False

    # Case 3: Needs renewal (expired, never set, or claimer timed out)
    return True
