"""
Shared helper: mint Firebase ID tokens for API integration tests.

Uses Firebase Admin SDK to create a custom token, then exchanges it
for a real ID token via the Firebase Auth REST API.  This gives us
an ID token that start_scenario's _verify_token() will accept.

Usage:
    from tests.helpers.firebase_auth import get_test_id_token
    token = get_test_id_token("michaeltreynolds.test@gmail.com")
"""

import os
import requests
import firebase_admin
from firebase_admin import auth as firebase_auth

PROJECT_ID = "pathway-email-bot-6543"

# Firebase Web API key (public, same as in portal/src/firebase-config.ts)
FIREBASE_API_KEY = "AIzaSyDj6y-LGt91jSR8l9H0kihm5jsf3c9uqBU"


def get_test_id_token(email: str) -> str:
    """
    Get a Firebase ID token for the given email.

    1. Ensures the user exists in Firebase Auth
    2. Creates a custom token via Admin SDK
    3. Exchanges it for an ID token via REST API
    """
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", PROJECT_ID)

    # Initialize Firebase Admin if needed
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": PROJECT_ID})

    # Get or create the test user
    try:
        user = firebase_auth.get_user_by_email(email)
    except firebase_auth.UserNotFoundError:
        user = firebase_auth.create_user(email=email, email_verified=True)

    # Create a custom token
    custom_token = firebase_auth.create_custom_token(user.uid)
    if isinstance(custom_token, bytes):
        custom_token = custom_token.decode("utf-8")

    # Exchange custom token for an ID token via Firebase Auth REST API
    resp = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}",
        json={"token": custom_token, "returnSecureToken": True},
    )
    resp.raise_for_status()
    return resp.json()["idToken"]
