#!/usr/bin/env python3
"""
Gmail Token Generator for PEB Service.

Runs the OAuth flow and stores the refresh token in GCP Secret Manager
(the single source of truth). No local files are created.

Usage:
    python scripts/get_token.py              # Interactive prompt
    python scripts/get_token.py --bot        # Bot account (pathwayemailbot@gmail.com)
    python scripts/get_token.py --test       # Test account (michaeltreynolds.test@gmail.com)

Prerequisites:
    - client_config.secret.json in repo root (run setup_dev.py first)
    - gcloud CLI authenticated
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from google_auth_oauthlib.flow import InstalledAppFlow

# Configuration
CLIENT_CONFIG_FILE = "client_config.secret.json"
PROJECT_ID = "pathway-email-bot-6543"

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]

ACCOUNTS = {
    "bot": {
        "email": "pathwayemailbot@gmail.com",
        "description": "Bot Gmail account (used by Cloud Function)",
        "gcp_secret": "gmail-refresh-token-bot",
    },
    "test": {
        "email": "michaeltreynolds.test@gmail.com",
        "description": "Test account (for automated testing)",
        "gcp_secret": "gmail-refresh-token-test",
    },
}


def print_header(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def run_oauth_flow() -> str | None:
    """Run OAuth flow and return refresh token."""
    if not os.path.exists(CLIENT_CONFIG_FILE):
        print(f"[ERROR] {CLIENT_CONFIG_FILE} not found.")
        print("Run: python scripts/setup_dev.py")
        return None

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_CONFIG_FILE, SCOPES)
    creds = flow.run_local_server(port=0, prompt='consent')

    if creds and creds.refresh_token:
        return creds.refresh_token
    else:
        print("[WARN] No refresh token returned. Try revoking access and re-authorizing.")
        return None


def store_in_gcp(secret_name: str, value: str, role: str) -> bool:
    """Store token in GCP Secret Manager with metadata."""
    print(f"\n[GCP] Storing in Secret Manager: {secret_name}")

    metadata = {
        "refresh_token": value,
        "generated_at": datetime.now().isoformat(),
        "role": role,
        "email": ACCOUNTS[role]["email"],
    }

    payload = json.dumps(metadata)

    try:
        # Check if secret exists
        result = subprocess.run(
            f'gcloud secrets describe "{secret_name}" 2>nul',
            capture_output=True, text=True, shell=True
        )

        if result.returncode != 0:
            print(f"  Creating new secret: {secret_name}")
            result = subprocess.run(
                f'gcloud secrets create "{secret_name}" --replication-policy=automatic',
                capture_output=True, text=True, shell=True
            )
            if result.returncode != 0:
                print(f"[ERROR] Failed to create secret: {result.stderr}")
                return False

        # Add new version
        result = subprocess.run(
            f'gcloud secrets versions add "{secret_name}" --data-file=-',
            input=payload, capture_output=True, text=True, shell=True
        )

        if result.returncode == 0:
            print(f"[OK] Stored in GCP Secret Manager")
            return True
        else:
            print(f"[ERROR] Failed to add version: {result.stderr}")
            return False

    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    if "--bot" in sys.argv:
        role = "bot"
    elif "--test" in sys.argv:
        role = "test"
    else:
        print_header("Gmail Token Generator")
        print("\nWhich account do you want to refresh?\n")
        print("  1. pathwayemailbot@gmail.com (bot - for Cloud Function)")
        print("  2. michaeltreynolds.test@gmail.com (test - for automated testing)")
        print()
        choice = input("Enter 1 or 2: ").strip()
        role = "bot" if choice == "1" else "test"

    info = ACCOUNTS[role]

    print_header(f"Refreshing Token: {role}")
    print(f"  Account: {info['email']}")
    print(f"  Secret:  {info['gcp_secret']}")

    # Step 1: OAuth Flow
    print(f"\n{'!'*60}")
    print(f"  SIGN IN WITH: {info['email']}")
    print(f"  Purpose: {info['description']}")
    print(f"{'!'*60}")
    print("\nBrowser will open automatically...")

    refresh_token = run_oauth_flow()

    if not refresh_token:
        print("\n[FAIL] Could not obtain refresh token")
        return 1

    print(f"\n[OK] Got refresh token: {refresh_token[:20]}...")

    # Step 2: Store in Secret Manager (single source of truth)
    if not store_in_gcp(info['gcp_secret'], refresh_token, role):
        print("[ERROR] Failed to store in Secret Manager!")
        return 1

    # Summary
    print_header("Complete")
    print(f"  Token for: {info['email']}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Secret Manager: {info['gcp_secret']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
