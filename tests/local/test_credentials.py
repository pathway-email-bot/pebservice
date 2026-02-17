"""
Local tests: credential and connectivity smoke tests.

Verifies that the current credentials (SA key or ADC) can access all
required GCP secrets, and that the bot's OAuth tokens are valid.  These
tests do NOT exercise any deployed service — they confirm that the
building blocks (secrets, Gmail API access) work from the caller's machine.

Run:  python -m pytest tests/local/test_credentials.py -v
"""

import time

import pytest

PROJECT_ID = "pathway-email-bot-6543"
BOT_EMAIL = "pathwayemailbot@gmail.com"

# Actual secret names in Secret Manager
SECRETS = {
    "openai-api-key": "OpenAI API key",
    "gmail-client-id": "Gmail OAuth client ID",
    "gmail-client-secret": "Gmail OAuth client secret",
    "gmail-refresh-token-bot": "Gmail bot refresh token",
    "gmail-refresh-token-test": "Gmail test account refresh token",
}


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def bot_gmail():
    """Authenticated Gmail API service for the bot account."""
    from tests.helpers.gmail_helpers import get_bot_gmail_service
    return get_bot_gmail_service()


# ── Tests: Secret Manager ───────────────────────────────────────────


class TestSecretManagerAccess:
    """Verify ADC credentials can read all required secrets."""

    def test_openai_api_key(self):
        from tests.helpers.gmail_helpers import get_secret
        key = get_secret("openai-api-key")
        assert key, "API key should not be empty"
        assert key.startswith("sk-"), f"Expected OpenAI key format, got: {key[:5]}..."

    @pytest.mark.parametrize("secret_name", list(SECRETS.keys()))
    def test_secret_exists_and_nonempty(self, secret_name):
        from tests.helpers.gmail_helpers import get_secret
        value = get_secret(secret_name)
        assert value, f"Secret '{secret_name}' ({SECRETS[secret_name]}) is empty"
        assert len(value) > 5, f"Secret '{secret_name}' looks too short: {len(value)} chars"


# ── Tests: Bot Gmail connectivity ────────────────────────────────────


class TestBotGmailConnectivity:
    """Verify bot Gmail credentials are valid and API calls succeed."""

    def test_bot_account_identity(self, bot_gmail):
        """Sanity: verify we're authenticated as the bot account."""
        profile = bot_gmail.users().getProfile(userId="me").execute()
        assert profile["emailAddress"] == BOT_EMAIL, (
            f"Expected {BOT_EMAIL}, got {profile['emailAddress']}"
        )

    def test_gmail_watch_call_succeeds(self, bot_gmail):
        """Direct watch() call succeeds and returns valid expiration."""
        response = bot_gmail.users().watch(
            userId="me",
            body={
                "labelIds": ["INBOX"],
                "topicName": f"projects/{PROJECT_ID}/topics/email-notifications",
            },
        ).execute()

        assert "historyId" in response, f"Missing historyId: {response}"
        assert "expiration" in response, f"Missing expiration: {response}"

        # Expiration should be a future timestamp (ms since epoch)
        exp_ms = int(response["expiration"])
        assert exp_ms > int(time.time() * 1000), "Expiration should be in the future"
