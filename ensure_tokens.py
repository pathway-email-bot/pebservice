#!/usr/bin/env python3
"""
Token management for PEB Service integration testing.

This script ensures all required tokens are present and valid:
1. gcloud CLI auth (owner account) - for Cloud Function logs
2. Gmail OAuth 'personal' role - for sending test emails  
3. Gmail OAuth 'bot' role (optional) - for verifying bot account

Usage:
    python ensure_tokens.py           # Check all tokens
    python ensure_tokens.py --refresh # Force refresh all tokens
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
TOKEN_STORE_FILE = "token_store.secret.json"
CLIENT_CONFIG_FILE = "client_config.secret.json"
GCLOUD_TOKEN_LIFETIME_HOURS = 1  # Access tokens last ~1 hour
GMAIL_REFRESH_TOKEN_CHECK_DAYS = 30  # Warn if older than this

# Account mapping - which email to use for each token type
ACCOUNT_MAP = {
    "gcloud": {
        "email": "michaeltreynolds@gmail.com",
        "description": "GCP Owner account for Cloud Function logs and deployment",
    },
    "gmail_personal": {
        "email": "michaeltreynolds@gmail.com", 
        "description": "Personal Gmail for sending test emails",
        "role": "personal",
    },
    "gmail_bot": {
        "email": "pathwayemailbot@gmail.com",
        "description": "Bot Gmail account (optional, for verification)",
        "role": "bot",
    },
}


def load_token_store() -> dict:
    """Load the token store from disk."""
    if os.path.exists(TOKEN_STORE_FILE):
        try:
            with open(TOKEN_STORE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"tokens": {}, "last_updated": None}


def save_token_store(store: dict):
    """Save the token store to disk."""
    store["last_updated"] = datetime.now().isoformat()
    with open(TOKEN_STORE_FILE, "w") as f:
        json.dump(store, f, indent=2)


def print_header(msg: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def print_account_warning(token_type: str):
    """Warn user which account to sign in with."""
    info = ACCOUNT_MAP.get(token_type, {})
    email = info.get("email", "unknown")
    desc = info.get("description", "")
    
    print(f"\n{'!'*60}")
    print(f"  SIGN IN WITH: {email}")
    print(f"  Purpose: {desc}")
    print(f"{'!'*60}")
    input("Press Enter when ready to open browser...")


def check_gcloud_auth() -> dict:
    """Check gcloud CLI authentication status."""
    result = {
        "valid": False,
        "account": None,
        "expires": None,
        "message": "",
    }
    
    try:
        # Check active account (use shell=True for Windows PATH resolution)
        proc = subprocess.run(
            'gcloud auth list --filter="status:ACTIVE" --format="value(account)"',
            capture_output=True, text=True, shell=True
        )
        account = proc.stdout.strip()
        
        if not account:
            result["message"] = "No active gcloud account"
            return result
        
        result["account"] = account
        
        # Verify it's the expected account
        expected = ACCOUNT_MAP["gcloud"]["email"]
        if account.lower() != expected.lower():
            result["message"] = f"Wrong account: {account} (expected {expected})"
            return result
        
        # Test access by describing a function
        proc = subprocess.run(
            'gcloud functions describe process_email --region=us-central1 --format="value(state)"',
            capture_output=True, text=True, shell=True
        )
        
        if proc.returncode == 0:
            result["valid"] = True
            result["message"] = f"Authenticated as {account}"
        else:
            result["message"] = f"Auth may be expired: {proc.stderr.strip()[:100]}"
            
    except FileNotFoundError:
        result["message"] = "gcloud CLI not installed"
    except Exception as e:
        result["message"] = f"Error: {e}"
    
    return result


def refresh_gcloud_auth():
    """Refresh gcloud authentication."""
    print_account_warning("gcloud")
    subprocess.run("gcloud auth login", shell=True, check=False)


def check_gmail_token(role: str) -> dict:
    """Check Gmail OAuth token status."""
    result = {
        "valid": False,
        "token_file": None,
        "created": None,
        "message": "",
    }
    
    token_file = f"token.{role}.secret.json"
    result["token_file"] = token_file
    
    # Check if client config exists
    if not os.path.exists(CLIENT_CONFIG_FILE):
        result["message"] = f"Missing {CLIENT_CONFIG_FILE}"
        return result
    
    # Check if token file exists
    if not os.path.exists(token_file):
        result["message"] = f"Token file not found: {token_file}"
        return result
    
    try:
        # Load and validate token file
        with open(token_file, "r") as f:
            data = json.load(f)
        
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            result["message"] = "No refresh_token in file"
            return result
        
        # Check file modification time
        mtime = os.path.getmtime(token_file)
        created = datetime.fromtimestamp(mtime)
        result["created"] = created.isoformat()
        
        age_days = (datetime.now() - created).days
        if age_days > GMAIL_REFRESH_TOKEN_CHECK_DAYS:
            result["message"] = f"Token is {age_days} days old (may need refresh)"
            result["valid"] = True  # Still technically valid
        else:
            result["valid"] = True
            result["message"] = f"Token found ({age_days} days old)"
            
    except (json.JSONDecodeError, IOError) as e:
        result["message"] = f"Error reading token: {e}"
    
    return result


def refresh_gmail_token(role: str):
    """Refresh Gmail OAuth token for a role."""
    token_type = f"gmail_{role}"
    print_account_warning(token_type)
    
    # Import here to avoid dependency issues if not installed
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.settings.basic'
        ]
        
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_CONFIG_FILE, SCOPES)
        creds = flow.run_local_server(port=0, prompt='consent')
        
        if creds and creds.refresh_token:
            token_file = f"token.{role}.secret.json"
            data = {
                "refresh_token": creds.refresh_token,
                "created": datetime.now().isoformat(),
            }
            with open(token_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"[OK] Saved token to {token_file}")
        else:
            print("[WARN] No refresh token returned")
            
    except ImportError:
        print("[ERROR] google_auth_oauthlib not installed. Run: pip install google-auth-oauthlib")
    except Exception as e:
        print(f"[ERROR] OAuth flow failed: {e}")


def main():
    force_refresh = "--refresh" in sys.argv
    
    print_header("PEB Service - Token Status Check")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Force refresh: {force_refresh}")
    
    store = load_token_store()
    all_valid = True
    
    # 1. Check gcloud auth
    print_header("1. gcloud CLI (for Cloud Function logs)")
    gcloud_status = check_gcloud_auth()
    
    status_icon = "[OK]" if gcloud_status["valid"] else "[!]"
    print(f"{status_icon} {gcloud_status['message']}")
    
    if not gcloud_status["valid"] or force_refresh:
        all_valid = False
        response = input("\nRefresh gcloud auth? (y/n): ").strip().lower()
        if response == "y":
            refresh_gcloud_auth()
            gcloud_status = check_gcloud_auth()
            print(f"After refresh: {gcloud_status['message']}")
    
    store["tokens"]["gcloud"] = gcloud_status
    
    # 2. Check Gmail personal token
    print_header("2. Gmail 'personal' (for sending test emails)")
    personal_status = check_gmail_token("personal")
    
    status_icon = "[OK]" if personal_status["valid"] else "[!]"
    print(f"{status_icon} {personal_status['message']}")
    
    if not personal_status["valid"] or force_refresh:
        all_valid = False
        response = input("\nRefresh 'personal' Gmail token? (y/n): ").strip().lower()
        if response == "y":
            refresh_gmail_token("personal")
            personal_status = check_gmail_token("personal")
            print(f"After refresh: {personal_status['message']}")
    
    store["tokens"]["gmail_personal"] = personal_status
    
    # 3. Check Gmail bot token (optional)
    print_header("3. Gmail 'bot' (optional, for bot account verification)")
    bot_status = check_gmail_token("bot")
    
    status_icon = "[OK]" if bot_status["valid"] else "[?]"
    print(f"{status_icon} {bot_status['message']}")
    print("(Bot token is optional for integration testing)")
    
    store["tokens"]["gmail_bot"] = bot_status
    
    # Save token store
    save_token_store(store)
    
    # Summary
    print_header("Summary")
    print(f"  gcloud:        {'[OK]' if gcloud_status['valid'] else '[MISSING]'}")
    print(f"  gmail_personal: {'[OK]' if personal_status['valid'] else '[MISSING]'}")
    print(f"  gmail_bot:      {'[OK]' if bot_status['valid'] else '[OPTIONAL]'}")
    print(f"\n  Token store saved to: {TOKEN_STORE_FILE}")
    
    if gcloud_status["valid"] and personal_status["valid"]:
        print("\n[SUCCESS] All required tokens are valid!")
        print("You can now run: python push_deploy_integration_test.py")
        return 0
    else:
        print("\n[WARN] Some tokens are missing or invalid")
        return 1


if __name__ == "__main__":
    sys.exit(main())
