#!/usr/bin/env python3
"""
Gmail Token Generator for PEB Service.

This script:
1. Runs OAuth flow to get a fresh Gmail refresh token
2. Stores the token in GCP Secret Manager (source of truth) with metadata
3. Syncs the token to GitHub Secrets
4. Updates local token file

Usage:
    python get_token.py              # Interactive - will prompt which account
    python get_token.py --bot        # Refresh bot token (pathwayemailbot@gmail.com)
    python get_token.py --personal   # Refresh personal token (michaeltreynolds@gmail.com)

The bot token is used by the Cloud Function to read/send emails.
The personal token is used locally for sending test emails.
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

# Account mapping
ACCOUNTS = {
    "bot": {
        "email": "pathwayemailbot@gmail.com",
        "description": "Bot Gmail account (used by Cloud Function)",
        "gcp_secret": "gmail-refresh-token-bot",
        "github_secret": "GMAIL_REFRESH_TOKEN",  # This is what the CF uses
        "local_file": "token.bot.secret.json",
    },
    "personal": {
        "email": "michaeltreynolds@gmail.com",
        "description": "Personal account (for testing)",
        "gcp_secret": "gmail-refresh-token-personal",
        "github_secret": None,  # Not synced to GitHub
        "local_file": "token.personal.secret.json",
    },
}


def print_header(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def print_account_warning(role: str):
    """Clearly indicate which account to sign in with."""
    info = ACCOUNTS.get(role, {})
    email = info.get("email", "unknown")
    desc = info.get("description", "")
    
    print(f"\n{'!'*60}")
    print(f"  SIGN IN WITH: {email}")
    print(f"  Purpose: {desc}")
    print(f"{'!'*60}")
    print("\nBrowser will open automatically...")


def run_oauth_flow() -> str | None:
    """Run OAuth flow and return refresh token."""
    if not os.path.exists(CLIENT_CONFIG_FILE):
        print(f"[ERROR] {CLIENT_CONFIG_FILE} not found.")
        print("Run: python sync_secrets.py")
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
    
    # Create metadata payload
    metadata = {
        "refresh_token": value,
        "generated_at": datetime.now().isoformat(),
        "role": role,
        "email": ACCOUNTS[role]["email"],
        # Gmail refresh tokens don't expire unless revoked, but we track generation time
        "notes": "Gmail refresh tokens have no fixed expiry - valid until revoked"
    }
    
    payload = json.dumps(metadata)
    
    try:
        # Check if secret exists
        result = subprocess.run(
            f'gcloud secrets describe "{secret_name}" 2>nul',
            capture_output=True, text=True, shell=True
        )
        
        if result.returncode != 0:
            # Create new secret
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


def sync_to_github(secret_name: str, value: str) -> bool:
    """Sync token to GitHub Secrets."""
    print(f"\n[GitHub] Syncing to: {secret_name}")
    
    try:
        result = subprocess.run(
            ["gh", "secret", "set", secret_name, "--body", value],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print(f"[OK] Synced to GitHub Secrets")
            return True
        else:
            print(f"[ERROR] {result.stderr}")
            return False
    except FileNotFoundError:
        print("[ERROR] gh CLI not installed")
        return False


def save_local(filename: str, value: str, role: str) -> bool:
    """Save token to local file with metadata."""
    print(f"\n[Local] Saving to: {filename}")
    
    data = {
        "refresh_token": value,
        "generated_at": datetime.now().isoformat(),
        "role": role,
        "email": ACCOUNTS[role]["email"],
    }
    
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"[OK] Saved locally")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def main():
    # Determine which role
    if "--bot" in sys.argv:
        role = "bot"
    elif "--personal" in sys.argv:
        role = "personal"
    else:
        print_header("Gmail Token Generator")
        print("\nWhich account do you want to refresh?\n")
        print("  1. pathwayemailbot@gmail.com (bot - for Cloud Function)")
        print("  2. michaeltreynolds@gmail.com (personal - for testing)")
        print()
        choice = input("Enter 1 or 2: ").strip()
        role = "bot" if choice == "1" else "personal"
    
    info = ACCOUNTS[role]
    
    print_header(f"Refreshing Token: {role}")
    print(f"  Account: {info['email']}")
    print(f"  GCP Secret: {info['gcp_secret']}")
    print(f"  GitHub Secret: {info['github_secret'] or 'N/A'}")
    print(f"  Local File: {info['local_file']}")
    
    # Step 1: OAuth Flow
    print_account_warning(role)
    refresh_token = run_oauth_flow()
    
    if not refresh_token:
        print("\n[FAIL] Could not obtain refresh token")
        return 1
    
    print(f"\n[OK] Got refresh token: {refresh_token[:20]}...")
    
    # Step 2: Store in GCP (source of truth)
    if not store_in_gcp(info['gcp_secret'], refresh_token, role):
        print("[WARN] Failed to store in GCP, continuing...")
    
    # Step 3: Sync to GitHub (if applicable)
    if info['github_secret']:
        if not sync_to_github(info['github_secret'], refresh_token):
            print("[WARN] Failed to sync to GitHub, continuing...")
    
    # Step 4: Save locally
    save_local(info['local_file'], refresh_token, role)
    
    # Summary
    print_header("Complete")
    print(f"  Token for: {info['email']}")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  GCP: {info['gcp_secret']}")
    if info['github_secret']:
        print(f"  GitHub: {info['github_secret']}")
    print(f"  Local: {info['local_file']}")
    
    if role == "bot":
        print("\n[NOTE] GitHub was updated. A new deployment will start automatically.")
        print("Run 'python wait_for_deploy.py' to monitor the deployment.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
