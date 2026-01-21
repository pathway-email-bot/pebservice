#!/usr/bin/env python3
"""
Secret Management for PEB Service.

GCP Secret Manager is the SOURCE OF TRUTH for all secrets.
This script syncs secrets from GCP to:
- Local dev environment (client_config.secret.json)
- GitHub Secrets (for CI/CD)

Usage:
    python sync_secrets.py              # Sync to local only
    python sync_secrets.py --github     # Also sync to GitHub Secrets
    python sync_secrets.py --list       # List all secrets in GCP

Prerequisites:
    - gcloud CLI authenticated as michaeltreynolds@gmail.com
    - gh CLI authenticated (for --github option)
"""

import json
import subprocess
import sys
import os

# Configuration
PROJECT_ID = "pathway-email-bot-6543"
CLIENT_CONFIG_FILE = "client_config.secret.json"

# Secrets stored in GCP Secret Manager
GCP_SECRETS = {
    "gmail-client-id": "GMAIL_CLIENT_ID",       # GCP name -> GitHub name
    "gmail-client-secret": "GMAIL_CLIENT_SECRET",
    # Add more secrets here as needed:
    # "openai-api-key": "OPENAI_API_KEY",
    # "gmail-refresh-token": "GMAIL_REFRESH_TOKEN",
}

# OAuth client config template
CLIENT_CONFIG_TEMPLATE = {
    "installed": {
        "client_id": "",
        "project_id": PROJECT_ID,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "",
        "redirect_uris": ["http://localhost"]
    }
}


def print_header(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def read_gcp_secret(name: str) -> str | None:
    """Read a secret from GCP Secret Manager."""
    try:
        result = subprocess.run(
            f'gcloud secrets versions access latest --secret="{name}"',
            capture_output=True, text=True, shell=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"[ERROR] Failed to read {name}: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Timeout reading {name}")
    except Exception as e:
        print(f"[ERROR] {e}")
    return None


def write_gcp_secret(name: str, value: str) -> bool:
    """Write a secret to GCP Secret Manager (creates new version)."""
    try:
        # Check if secret exists
        result = subprocess.run(
            f'gcloud secrets describe "{name}" 2>/dev/null',
            capture_output=True, text=True, shell=True
        )
        
        if result.returncode != 0:
            # Create new secret
            result = subprocess.run(
                f'gcloud secrets create "{name}" --replication-policy=automatic',
                capture_output=True, text=True, shell=True
            )
            if result.returncode != 0:
                print(f"[ERROR] Failed to create secret {name}")
                return False
        
        # Add new version
        result = subprocess.run(
            f'gcloud secrets versions add "{name}" --data-file=-',
            input=value, capture_output=True, text=True, shell=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def set_github_secret(name: str, value: str) -> bool:
    """Set a secret in GitHub."""
    try:
        result = subprocess.run(
            ["gh", "secret", "set", name, "--body", value],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def list_secrets():
    """List all secrets in GCP Secret Manager."""
    print_header("GCP Secret Manager - Secrets")
    result = subprocess.run(
        'gcloud secrets list --format="table(name,createTime)"',
        shell=True
    )
    return result.returncode == 0


def sync_to_local() -> bool:
    """Sync secrets from GCP to local client_config.secret.json."""
    print_header("Syncing to Local Environment")
    
    client_id = read_gcp_secret("gmail-client-id")
    client_secret = read_gcp_secret("gmail-client-secret")
    
    if not client_id or not client_secret:
        print("[ERROR] Failed to read required secrets from GCP")
        return False
    
    # Create client config
    config = CLIENT_CONFIG_TEMPLATE.copy()
    config["installed"] = CLIENT_CONFIG_TEMPLATE["installed"].copy()
    config["installed"]["client_id"] = client_id
    config["installed"]["client_secret"] = client_secret
    
    with open(CLIENT_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"[OK] Created {CLIENT_CONFIG_FILE}")
    print(f"     Client ID: {client_id[:20]}...")
    return True


def sync_to_github() -> bool:
    """Sync secrets from GCP to GitHub Secrets."""
    print_header("Syncing to GitHub Secrets")
    
    # Check gh CLI
    result = subprocess.run(["gh", "--version"], capture_output=True)
    if result.returncode != 0:
        print("[ERROR] GitHub CLI (gh) not installed")
        return False
    
    all_ok = True
    for gcp_name, github_name in GCP_SECRETS.items():
        value = read_gcp_secret(gcp_name)
        if value:
            if set_github_secret(github_name, value):
                print(f"[OK] {github_name} synced to GitHub")
            else:
                print(f"[ERROR] Failed to sync {github_name}")
                all_ok = False
        else:
            print(f"[SKIP] {gcp_name} not found in GCP")
    
    return all_ok


def main():
    list_only = "--list" in sys.argv
    sync_github = "--github" in sys.argv
    
    print("=" * 60)
    print("  PEB Service - Secret Sync")
    print("  Source of Truth: GCP Secret Manager")
    print("=" * 60)
    
    if list_only:
        return 0 if list_secrets() else 1
    
    # Always sync to local
    if not sync_to_local():
        return 1
    
    # Optionally sync to GitHub
    if sync_github:
        if not sync_to_github():
            return 1
    
    print_header("Summary")
    print("[OK] Secrets synced from GCP Secret Manager")
    if sync_github:
        print("[OK] GitHub Secrets updated")
    print(f"\nLocal file: {CLIENT_CONFIG_FILE}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
