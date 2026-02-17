"""
Local test: _ensure_watch() function against real GCP services.

Verifies the full _ensure_watch flow:
  - Firestore transaction (claim/complete in system/watch_status)
  - Gmail watch() API call (renews push notifications)

This tests OUR code logic (not just raw API calls) against live services.

Credentials:
  - SA (test-runner-key or CI): reads secrets from Secret Manager
  - Bot OAuth: built from gmail-client-id/secret + refresh-token-bot

Run:  python -m pytest tests/local/test_watch.py -v --timeout=30
Cost: 1 Firestore read/write + 1 Gmail watch() call (free tier)
"""

import pytest

PROJECT_ID = "pathway-email-bot-6543"


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def bot_gmail():
    """Authenticated Gmail API service for the bot account."""
    from tests.helpers.gmail_helpers import get_bot_gmail_service
    return get_bot_gmail_service()


@pytest.fixture(scope="module")
def db():
    """Firestore client for the 'pathway' database."""
    from tests.helpers.firestore_helpers import get_firestore_db
    return get_firestore_db()


# ── Tests ────────────────────────────────────────────────────────────


class TestEnsureWatch:
    """Verify _ensure_watch() writes correct Firestore status."""

    def test_firestore_watch_status_document(self, bot_gmail, db):
        """_ensure_watch writes correct status to Firestore."""
        from datetime import datetime, timezone

        # Import and call _ensure_watch (the real function)
        from service.main import _ensure_watch
        import service.main as main_module

        # Force a fresh check by clearing the in-memory cache
        original_cache = main_module._watch_expires_at
        try:
            main_module._watch_expires_at = None
            _ensure_watch(bot_gmail)
        finally:
            main_module._watch_expires_at = original_cache

        # Verify Firestore doc was written
        doc = db.collection("system").document("watch_status").get()
        assert doc.exists, "system/watch_status document should exist"

        data = doc.to_dict()
        assert data["status"] == "completed", f"Expected 'completed', got '{data['status']}'"
        assert "expires_at" in data, "Missing expires_at field"
        assert "completed_at" in data, "Missing completed_at field"

        # expires_at should be in the future (within 7 days).
        # The watch may have been renewed earlier, so we only check
        # it hasn't expired yet — not that it's exactly ~7 days out.
        expires_at = data["expires_at"]
        if not expires_at.tzinfo:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        days_until_expiry = (expires_at - now).total_seconds() / 86400
        assert 0 < days_until_expiry <= 7.1, (
            f"Expected expiry in the future (<=7 days), got {days_until_expiry:.1f}"
        )
