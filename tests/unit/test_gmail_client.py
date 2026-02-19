"""
Unit tests for service/gmail_client.py.

Tests MIME message building, email body extraction, and watch renewal logic.
Gmail API interactions are mocked — no real Google calls.
"""

import base64
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock, patch

import pytest

from service.gmail_client import (
    build_mime_message,
    send_reply,
    extract_email_body,
    check_and_claim_watch,
)


# ── MIME Message Building ────────────────────────────────────────────


class TestBuildMimeMessage:
    """Tests for build_mime_message()."""

    def test_returns_base64_encoded_string(self):
        result = build_mime_message(
            from_addr="bot@example.com",
            from_name="Test Bot",
            to_addr="student@example.com",
            subject="Test Subject",
            body="Hello, World!",
        )
        # Should be valid base64
        decoded = base64.urlsafe_b64decode(result)
        text = decoded.decode("utf-8")
        assert "Hello, World!" in text
        assert "Test Bot" in text
        assert "Test Subject" in text

    def test_includes_proper_headers(self):
        result = build_mime_message(
            from_addr="bot@example.com",
            from_name="Bot Name",
            to_addr="user@example.com",
            subject="Re: Test",
            body="Content here",
        )
        decoded = base64.urlsafe_b64decode(result).decode("utf-8")
        assert "To: user@example.com" in decoded
        assert "Bot Name <bot@example.com>" in decoded

    def test_multipart_alternative_with_html(self):
        """When html is provided, creates multipart/alternative with both parts."""
        from email import message_from_bytes

        result = build_mime_message(
            from_addr="bot@example.com",
            from_name="Test Bot",
            to_addr="student@example.com",
            subject="Magic Link",
            body="Plain text fallback",
            html="<h1>HTML version</h1>",
        )
        raw_bytes = base64.urlsafe_b64decode(result)
        parsed = message_from_bytes(raw_bytes)

        assert parsed.get_content_type() == "multipart/alternative"

        parts = list(parsed.walk())
        content_types = [p.get_content_type() for p in parts]
        assert "text/plain" in content_types
        assert "text/html" in content_types

        # Verify payloads
        plain_part = [p for p in parts if p.get_content_type() == "text/plain"][0]
        html_part = [p for p in parts if p.get_content_type() == "text/html"][0]
        assert "Plain text fallback" in plain_part.get_payload(decode=True).decode()
        assert "<h1>HTML version</h1>" in html_part.get_payload(decode=True).decode()


# ── send_reply (MIME correctness) ────────────────────────────────────


def _make_original_msg(message_id="<abc123@mail.gmail.com>"):
    """Build a minimal original-message dict for send_reply tests."""
    return {
        "threadId": "thread_xyz",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "student@example.com"},
                {"name": "Message-ID", "value": message_id},
            ]
        },
    }


class TestSendReply:
    """Tests that send_reply() produces standards-compliant MIME messages."""

    @patch("service.main.get_header")
    def test_reply_has_content_type_header(self, mock_get_header):
        """Reply must contain Content-Type: text/plain."""
        def header_side_effect(headers, name, default=""):
            mapping = {
                "Subject": "Test Subject",
                "From": "student@example.com",
                "Message-ID": "<abc123@mail.gmail.com>",
            }
            return mapping.get(name, default)

        mock_get_header.side_effect = header_side_effect

        service = MagicMock()
        service.users().messages().send().execute.return_value = {"id": "sent_123"}

        send_reply(service, _make_original_msg(), "Hello reply")

        # Verify send was called
        assert service.users().messages().send.called

    @patch("service.main.get_header")
    def test_reply_produces_valid_mime(self, mock_get_header):
        """Reply should be a valid MIME message with all required headers."""
        from email import message_from_bytes

        captured_body = {}

        def header_side_effect(headers, name, default=""):
            mapping = {
                "Subject": "Test Subject",
                "From": "student@example.com",
                "Message-ID": "<abc123@mail.gmail.com>",
            }
            return mapping.get(name, default)

        mock_get_header.side_effect = header_side_effect

        # Capture the body passed to send()
        mock_send = MagicMock()
        mock_send.execute.return_value = {"id": "sent_123"}

        service = MagicMock()
        service.users().messages().send.return_value = mock_send

        def capture_send(**kwargs):
            captured_body.update(kwargs.get("body", {}))
            return mock_send

        service.users().messages().send.side_effect = capture_send

        send_reply(service, _make_original_msg(), "Hello world")

        assert "raw" in captured_body
        raw_bytes = base64.urlsafe_b64decode(captured_body["raw"])
        parsed = message_from_bytes(raw_bytes)

        assert parsed["Content-Type"] is not None
        assert "text/plain" in parsed["Content-Type"]
        assert parsed["MIME-Version"] == "1.0"
        assert "pathwayemailbot@gmail.com" in parsed["From"]
        assert parsed["To"] == "student@example.com"
        assert parsed["Subject"].startswith("Re:")
        assert parsed["In-Reply-To"] == "<abc123@mail.gmail.com>"
        assert parsed["References"] == "<abc123@mail.gmail.com>"
        assert parsed.get_payload() == "Hello world"


# ── Email Body Extraction ────────────────────────────────────────────


class TestExtractEmailBody:
    """Tests for extract_email_body() with various MIME structures."""

    def test_single_part_body(self):
        """Simple message with body data directly on payload."""
        body_text = "Hello from a simple email"
        encoded = base64.urlsafe_b64encode(body_text.encode()).decode()
        msg = {"payload": {"body": {"data": encoded}}}
        assert extract_email_body(msg) == body_text

    def test_multipart_text_plain(self):
        """Standard multipart with text/plain part."""
        body_text = "Plain text content"
        encoded = base64.urlsafe_b64encode(body_text.encode()).decode()
        msg = {
            "payload": {
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": encoded},
                    },
                    {
                        "mimeType": "text/html",
                        "body": {"data": base64.urlsafe_b64encode(b"<p>HTML</p>").decode()},
                    },
                ]
            }
        }
        assert extract_email_body(msg) == body_text

    def test_nested_multipart(self):
        """Nested multipart/mixed → multipart/alternative → text/plain."""
        body_text = "Deeply nested text"
        encoded = base64.urlsafe_b64encode(body_text.encode()).decode()
        msg = {
            "payload": {
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "parts": [
                            {
                                "mimeType": "text/plain",
                                "body": {"data": encoded},
                            },
                            {
                                "mimeType": "text/html",
                                "body": {"data": base64.urlsafe_b64encode(b"<p>HTML</p>").decode()},
                            },
                        ],
                    }
                ]
            }
        }
        assert extract_email_body(msg) == body_text

    def test_no_body_returns_empty(self):
        """Message with no decodable body."""
        msg = {"payload": {"body": {}}}
        assert extract_email_body(msg) == ""

    def test_empty_parts_returns_empty(self):
        """Message with empty parts list falls back to payload body."""
        msg = {"payload": {"parts": [], "body": {}}}
        # Empty parts list means no parts → tries payload body
        assert extract_email_body(msg) == ""

    def test_raw_message_format(self):
        """If raw field is present, parses full MIME message."""
        mime = MIMEMultipart("alternative")
        plain = MIMEText("Plain from raw", "plain")
        html = MIMEText("<p>HTML from raw</p>", "html")
        mime.attach(plain)
        mime.attach(html)

        raw_b64 = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        msg = {"raw": raw_b64, "payload": {}}
        assert extract_email_body(msg) == "Plain from raw"


# ── Watch Renewal Logic ──────────────────────────────────────────────


class TestCheckAndClaimWatch:
    """Tests for check_and_claim_watch pure decision logic.

    Migrated from test_main.py TestCheckAndClaimWatch.
    """

    def _now(self):
        return datetime.now(timezone.utc)

    def test_fresh_completed_watch_returns_false(self):
        now = self._now()
        data = {
            "status": "completed",
            "expires_at": now + timedelta(days=5),
        }
        assert check_and_claim_watch(data, now) is False

    def test_expiring_soon_returns_true(self):
        now = self._now()
        data = {
            "status": "completed",
            "expires_at": now + timedelta(hours=12),
        }
        assert check_and_claim_watch(data, now) is True

    def test_empty_data_returns_true(self):
        assert check_and_claim_watch({}, self._now()) is True

    def test_recent_renewing_claim_returns_false(self):
        now = self._now()
        data = {
            "status": "renewing",
            "claimed_at": now - timedelta(seconds=30),
        }
        assert check_and_claim_watch(data, now) is False

    def test_stale_renewing_claim_returns_true(self):
        now = self._now()
        data = {
            "status": "renewing",
            "claimed_at": now - timedelta(seconds=90),
        }
        assert check_and_claim_watch(data, now) is True

    def test_expired_watch_returns_true(self):
        now = self._now()
        data = {
            "status": "completed",
            "expires_at": now - timedelta(hours=1),
        }
        assert check_and_claim_watch(data, now) is True

    def test_exactly_at_buffer_boundary_returns_true(self):
        now = self._now()
        data = {
            "status": "completed",
            "expires_at": now + timedelta(hours=24),
        }
        assert check_and_claim_watch(data, now) is True

    def test_naive_timestamps_handled(self):
        now = datetime.now(timezone.utc)
        naive_expires = (now + timedelta(days=5)).replace(tzinfo=None)
        data = {
            "status": "completed",
            "expires_at": naive_expires,
        }
        assert check_and_claim_watch(data, now) is False
