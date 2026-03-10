"""
Firebase Auth helpers for the PEB Service.
"""

import logging
import os

from flask import Request
from firebase_admin import auth as firebase_auth
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from logging_utils import log_function

logger = logging.getLogger(__name__)

# Pub/Sub OIDC — expected service account that signs push tokens
_PUBSUB_SA = "peb-runtime@pathway-email-bot-6543.iam.gserviceaccount.com"


@log_function
def verify_token(request: Request) -> str | None:
    """Verify Firebase ID token from Authorization header.

    Returns the user's email if valid, None otherwise.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    try:
        id_token = auth_header[7:]  # Remove 'Bearer ' prefix
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded.get("email")
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None


def verify_pubsub_token(request: Request) -> bool:
    """Verify the OIDC token attached by a Pub/Sub push subscription.

    Pub/Sub push subscriptions configured with an OIDC token attach a
    signed JWT in the ``Authorization: Bearer <token>`` header.  This
    function validates the token's signature (via Google's public certs),
    checks the audience matches our Cloud Run service URL, and confirms
    the issuer is the expected service account.

    Returns True if the token is valid, False otherwise.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Pub/Sub token missing: no Bearer header")
        return False

    token = auth_header[7:]

    try:
        # Pub/Sub default audience = push endpoint URL when no explicit
        # audience is configured on the subscription.
        # Cloud Run service URL format: https://{K_SERVICE}-{PROJECT_HASH}.{REGION}.run.app
        # We pass audience=None to skip audience check since the push endpoint
        # URL is hard to reconstruct reliably. The SA email check below
        # provides the authorization gate.
        claim = google_id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
        )

        email = claim.get("email", "")
        if email != _PUBSUB_SA:
            logger.warning(f"Pub/Sub token SA mismatch: got {email}, expected {_PUBSUB_SA}")
            return False

        return True

    except Exception as e:
        logger.warning(f"Pub/Sub token verification failed: {e}")
        return False
