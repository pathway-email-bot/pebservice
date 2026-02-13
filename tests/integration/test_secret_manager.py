"""
Integration test: Secret Manager access.

Verifies we can read the secrets needed by the PEB service from Google Cloud
Secret Manager. Works both locally (via `gcloud auth application-default login`)
and in CI (via the GCP_SA_KEY service account).

Run: python -m pytest tests/integration/test_secret_manager.py -v
"""

import pytest

PROJECT_ID = "pathway-email-bot-6543"

# Actual secret names in Secret Manager
SECRETS = {
    "openai-api-key": "OpenAI API key",
    "gmail-client-id": "Gmail OAuth client ID",
    "gmail-client-secret": "Gmail OAuth client secret",
    "gmail-refresh-token-bot": "Gmail bot refresh token",
    "gmail-refresh-token-test": "Gmail test account refresh token",
}


def _get_secret(name: str) -> str:
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    full_name = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
    response = client.access_secret_version(request={"name": full_name})
    return response.payload.data.decode("UTF-8").strip()


class TestSecretManagerAccess:
    """Verify ADC credentials can read all required secrets."""

    def test_openai_api_key(self):
        key = _get_secret("openai-api-key")
        assert key, "API key should not be empty"
        assert key.startswith("sk-"), f"Expected OpenAI key format, got: {key[:5]}..."

    @pytest.mark.parametrize("secret_name", list(SECRETS.keys()))
    def test_secret_exists_and_nonempty(self, secret_name):
        value = _get_secret(secret_name)
        assert value, f"Secret '{secret_name}' ({SECRETS[secret_name]}) is empty"
        assert len(value) > 5, f"Secret '{secret_name}' looks too short: {len(value)} chars"
