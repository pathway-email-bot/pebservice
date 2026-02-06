#!/usr/bin/env python3
"""Test OAuth using Secret Manager - same as Cloud Function does."""

import subprocess
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Fetch secrets the same way Cloud Function does (from Secret Manager)
result_id = subprocess.run(
    'gcloud secrets versions access latest --secret=gmail-client-id',
    capture_output=True, text=True, check=True, shell=True
)
client_id = result_id.stdout.strip()

result_secret = subprocess.run(
    'gcloud secrets versions access latest --secret=gmail-client-secret',
    capture_output=True, text=True, check=True, shell=True
)
client_secret = result_secret.stdout.strip()

result_token = subprocess.run(
    'gcloud secrets versions access latest --secret=gmail-refresh-token-bot',
    capture_output=True, text=True, check=True, shell=True
)
refresh_token_raw = result_token.stdout.strip()

# Parse the JSON to get just the refresh_token field
import json
token_data = json.loads(refresh_token_raw)
refresh_token = token_data['refresh_token']

print(f"Client ID length: {len(client_id)}")
print(f"Client ID: {client_id}")
print(f"Client Secret length: {len(client_secret)}")
print(f"Client Secret: {client_secret[:20]}...")
print(f"Refresh Token length: {len(refresh_token)}")
print(f"Refresh Token: {refresh_token[:30]}...")

# Try to use them
creds = Credentials(
    None,
    refresh_token=refresh_token,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret
)

try:
    creds.refresh(Request())
    print("\n✓ OAuth WORKS with Secret Manager secrets!")
    print(f"Access token: {creds.token[:30]}...")
except Exception as e:
    print(f"\n✗ OAuth FAILED with Secret Manager secrets!")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
