"""
Centralised Secret Manager access for the PEB Service.

Provides cached access to GCP project ID and secrets so that callers
don't each independently construct Secret Manager clients.
"""


import logging
import os

from google.cloud import secretmanager

from .logging_utils import log_function

logger = logging.getLogger(__name__)

# Module-level caches
_sm_client: secretmanager.SecretManagerServiceClient | None = None
_project_id: str | None = None


def _get_sm_client() -> secretmanager.SecretManagerServiceClient:
    """Return a cached Secret Manager client."""
    global _sm_client
    if _sm_client is None:
        _sm_client = secretmanager.SecretManagerServiceClient()
    return _sm_client


@log_function
def get_project_id() -> str:
    """Resolve and cache the GCP project ID.

    Resolution order:
      1. GCP_PROJECT env var
      2. GOOGLE_CLOUD_PROJECT env var
      3. GCP metadata server (Cloud Functions runtime)
    """
    global _project_id
    if _project_id is not None:
        return _project_id

    _project_id = os.environ.get("GCP_PROJECT") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    if _project_id:
        return _project_id

    # Fallback: metadata service (only works on GCP)
    import requests

    metadata_server = (
        "http://metadata.google.internal/computeMetadata/v1/project/project-id"
    )
    _project_id = requests.get(
        metadata_server, headers={"Metadata-Flavor": "Google"}
    ).text
    return _project_id


@log_function
def get_secret(secret_id: str) -> str:
    """Fetch a secret value from Secret Manager.

    Returns the decoded, whitespace-stripped payload.
    """
    client = _get_sm_client()
    project_id = get_project_id()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8").strip()


@log_function
def get_openai_api_key() -> str | None:
    """Return the OpenAI API key (Secret Manager → env var fallback)."""
    try:
        return get_secret("openai-api-key")
    except Exception as e:
        logger.error(f"Failed to fetch OpenAI API key from Secret Manager: {e}")
        key = os.environ.get("OPENAI_API_KEY")
        return key.strip() if key else None


def _reset_caches():
    """Reset module-level caches (for testing only)."""
    global _sm_client, _project_id
    _sm_client = None
    _project_id = None
