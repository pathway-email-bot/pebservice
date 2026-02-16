"""
Unit tests for service/main.py helper functions.

Tests get_header (case-insensitive header lookup) and watch renewal
(distributed Gmail watch renewal) without any external service dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from service.main import get_header, _check_and_claim_watch


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


class TestCheckAndClaimWatch:
    """Tests for _check_and_claim_watch pure decision logic.

    This is the core logic extracted from the Firestore transaction,
    so it can be tested without any mocks.
    """

    def _now(self):
        return datetime.now(timezone.utc)

    def test_fresh_completed_watch_returns_false(self):
        """If watch is completed and not expiring soon, skip renewal."""
        now = self._now()
        data = {
            'status': 'completed',
            'expires_at': now + timedelta(days=5),  # 5 days left > 24h buffer
        }
        assert _check_and_claim_watch(data, now) is False

    def test_expiring_soon_returns_true(self):
        """If watch expires within 24h, claim renewal."""
        now = self._now()
        data = {
            'status': 'completed',
            'expires_at': now + timedelta(hours=12),  # 12h left < 24h buffer
        }
        assert _check_and_claim_watch(data, now) is True

    def test_empty_data_returns_true(self):
        """If watch_status doc doesn't exist (empty data), claim renewal."""
        assert _check_and_claim_watch({}, self._now()) is True

    def test_recent_renewing_claim_returns_false(self):
        """If another instance claimed < 60s ago, skip."""
        now = self._now()
        data = {
            'status': 'renewing',
            'claimed_at': now - timedelta(seconds=30),  # 30s ago < 60s timeout
        }
        assert _check_and_claim_watch(data, now) is False

    def test_stale_renewing_claim_returns_true(self):
        """If a claim is older than 60s (claimer probably crashed), reclaim."""
        now = self._now()
        data = {
            'status': 'renewing',
            'claimed_at': now - timedelta(seconds=90),  # 90s ago > 60s timeout
        }
        assert _check_and_claim_watch(data, now) is True

    def test_expired_watch_returns_true(self):
        """If watch already expired, claim renewal."""
        now = self._now()
        data = {
            'status': 'completed',
            'expires_at': now - timedelta(hours=1),  # already expired
        }
        assert _check_and_claim_watch(data, now) is True

    def test_exactly_at_buffer_boundary_returns_true(self):
        """If expires_at == now + 24h exactly, that is NOT > buffer, so claim."""
        now = self._now()
        data = {
            'status': 'completed',
            'expires_at': now + timedelta(hours=24),  # exactly at boundary
        }
        assert _check_and_claim_watch(data, now) is True

    def test_naive_timestamps_handled(self):
        """Naive (no tzinfo) timestamps from Firestore are treated as UTC."""
        now = datetime.now(timezone.utc)
        naive_expires = (now + timedelta(days=5)).replace(tzinfo=None)
        data = {
            'status': 'completed',
            'expires_at': naive_expires,
        }
        assert _check_and_claim_watch(data, now) is False


class TestEnsureWatch:
    """Tests for _ensure_watch end-to-end orchestration."""

    def test_skips_when_memory_cache_fresh(self):
        """If module-level cache says watch is fresh, no DB or API calls."""
        import service.main as main_module
        from service.main import _ensure_watch

        mock_service = MagicMock()
        original = main_module._watch_expires_at

        try:
            main_module._watch_expires_at = datetime.now(timezone.utc) + timedelta(days=5)
            _ensure_watch(mock_service)
            # Gmail API should NOT be called
            mock_service.users.assert_not_called()
        finally:
            main_module._watch_expires_at = original



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

