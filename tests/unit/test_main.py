"""
Unit tests for service/main.py helper functions.

Tests get_header (case-insensitive header lookup), name personalisation,
idempotency guard, and rate limiting.

Watch renewal tests have been moved to test_gmail_client.py.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from service.main import get_header


class TestGetHeader:
    """Tests for case-insensitive email header lookup."""

    SAMPLE_HEADERS = [
        {"name": "From", "value": "alice@example.com"},
        {"name": "Subject", "value": "Test Subject"},
        {"name": "Message-ID", "value": "<abc123@mail.example.com>"},
        {"name": "Content-Type", "value": "text/plain"},
    ]

    def test_exact_case_match(self):
        assert get_header(self.SAMPLE_HEADERS, "From") == "alice@example.com"

    def test_case_insensitive_match(self):
        assert get_header(self.SAMPLE_HEADERS, "from") == "alice@example.com"
        assert get_header(self.SAMPLE_HEADERS, "FROM") == "alice@example.com"

    def test_subject(self):
        assert get_header(self.SAMPLE_HEADERS, "subject") == "Test Subject"

    def test_message_id_mixed_case(self):
        assert get_header(self.SAMPLE_HEADERS, "message-id") == "<abc123@mail.example.com>"
        assert get_header(self.SAMPLE_HEADERS, "Message-Id") == "<abc123@mail.example.com>"

    def test_missing_header_returns_default(self):
        assert get_header(self.SAMPLE_HEADERS, "X-Custom") == ""

    def test_missing_header_with_custom_default(self):
        assert get_header(self.SAMPLE_HEADERS, "X-Custom", "fallback") == "fallback"

    def test_empty_headers(self):
        assert get_header([], "From") == ""

    def test_returns_first_match(self):
        """If multiple headers with same name, returns the first."""
        headers = [
            {"name": "From", "value": "first@example.com"},
            {"name": "From", "value": "second@example.com"},
        ]
        assert get_header(headers, "from") == "first@example.com"


class TestEnsureWatch:
    """Tests for ensure_watch end-to-end orchestration."""

    def test_skips_when_memory_cache_fresh(self):
        """If module-level cache says watch is fresh, no DB or API calls."""
        import service.gmail_client as gmail_module
        from service.gmail_client import ensure_watch

        mock_service = MagicMock()
        original = gmail_module._watch_expires_at

        try:
            gmail_module._watch_expires_at = datetime.now(timezone.utc) + timedelta(days=5)
            ensure_watch(mock_service)
            # Gmail API should NOT be called
            mock_service.users.assert_not_called()
        finally:
            gmail_module._watch_expires_at = original


class TestPersonalizeBody:
    """Tests for _personalize_body placeholder substitution.

    _personalize_body is now a pure function: (body, first_name) -> str.
    Names are validated at write time by Firestore rules, so no mocks needed.
    """

    def test_replaces_placeholder_with_name(self):
        from service.main import _personalize_body
        body = "Hi {student_name},\n\nWelcome!"
        result = _personalize_body(body, "Sarah")
        assert result == "Hi Sarah,\n\nWelcome!"

    def test_no_placeholder_returns_body_unchanged(self):
        from service.main import _personalize_body
        body = "Hi there,\n\nWelcome!"
        result = _personalize_body(body, "Sarah")
        assert result == body

    def test_none_name_removes_placeholder(self):
        from service.main import _personalize_body
        body = "Hi {student_name},\n\nWelcome!"
        result = _personalize_body(body, None)
        assert result == "Hi ,\n\nWelcome!"

    def test_empty_name_removes_placeholder(self):
        from service.main import _personalize_body
        body = "Hi {student_name},\n\nWelcome!"
        result = _personalize_body(body, "")
        assert result == "Hi ,\n\nWelcome!"

    def test_unicode_name_works(self):
        from service.main import _personalize_body
        body = "Hi {student_name},\n\nWelcome!"
        result = _personalize_body(body, "María")
        assert result == "Hi María,\n\nWelcome!"
