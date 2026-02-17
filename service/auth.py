"""
Firebase Auth helpers for the PEB Service.
"""

import logging

from flask import Request
from firebase_admin import auth as firebase_auth

from .logging_utils import log_function

logger = logging.getLogger(__name__)


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
