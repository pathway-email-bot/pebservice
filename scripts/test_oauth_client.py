#!/usr/bin/env python3
"""Test if the OAuth client credentials are valid."""

import json
from google.oauth2.credentials import Credentials

# Load credentials
with open('config/client_config.secret.json') as f:
    client_config = json.load(f)
    client_id = client_config['installed']['client_id']
    client_secret = client_config['installed']['client_secret']

with open('token.bot.secret.json') as f:
    token_data = json.load(f)
    refresh_token = token_data['refresh_token']

print(f"Client ID: {client_id}")
print(f"Client Secret: {client_secret[:20]}...")
print(f"Refresh Token: {refresh_token[:30]}...")

# Try to refresh the token
creds = Credentials(
    None,
    refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret
)

try:
    # This will trigger a token refresh
    from google.auth.transport.requests import Request
    creds.refresh(Request())
    print("\n✓ OAuth client is VALID - token refresh succeeded")
    print(f"Access token: {creds.token[:30]}...")
except Exception as e:
    print(f"\n✗ OAuth client is INVALID - {e}")
    print("\nThe OAuth client has likely been deleted from Google Cloud Console.")
    print("You need to:")
    print("1. Go to: https://console.cloud.google.com/apis/credentials?project=pathway-email-bot-6543")
    print("2. Create new OAuth 2.0 Client ID (Desktop app)")
    print("3. Download JSON and replace config/client_config.secret.json")
    print("4. Run: python scripts/get_token.py --bot")
    print("5. Update Secret Manager with new credentials")
