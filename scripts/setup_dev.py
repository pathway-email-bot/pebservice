#!/usr/bin/env python3
"""
Developer machine setup for PEB Service.

Run this after cloning the repo to get everything ready:
  1. Creates a Python virtual environment
  2. Installs all dependencies (service + test)
  3. Generates client_config.secret.json from Secret Manager
  4. Downloads the test-runner SA key (for running tests locally)

Prerequisites:
  - Python 3.11+
  - gcloud CLI authenticated as michaeltreynolds@gmail.com
  - gcloud project set: gcloud config set project pathway-email-bot-6543

Usage:
    python scripts/setup_dev.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ID = "pathway-email-bot-6543"
TEST_RUNNER_SA = f"peb-test-runner@{PROJECT_ID}.iam.gserviceaccount.com"
REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
CLIENT_CONFIG_FILE = REPO_ROOT / "client_config.secret.json"
TEST_RUNNER_KEY_FILE = REPO_ROOT / "test-runner-key.secret.json"

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


def header(msg: str):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def run(cmd: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, **kwargs)


def read_secret(name: str) -> str | None:
    result = run(f'gcloud secrets versions access latest --secret="{name}" --project={PROJECT_ID}')
    if result.returncode == 0:
        return result.stdout.strip()
    print(f"  [ERROR] Failed to read {name}: {result.stderr.strip()}")
    return None


# ── Step 1: Virtual Environment ──────────────────────────────────────

def setup_venv():
    header("Step 1: Virtual Environment")

    if VENV_DIR.exists():
        print(f"  [OK] .venv already exists")
    else:
        print(f"  Creating .venv...")
        result = run(f"{sys.executable} -m venv {VENV_DIR}")
        if result.returncode != 0:
            print(f"  [ERROR] {result.stderr}")
            return False
        print(f"  [OK] Created .venv")

    # Determine pip path
    pip = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / "pip"

    print(f"  Installing service dependencies...")
    result = run(f"{pip} install -r service/requirements.txt -q")
    if result.returncode != 0:
        print(f"  [WARN] {result.stderr.strip()[:200]}")

    print(f"  Installing test dependencies...")
    result = run(f"{pip} install -r tests/requirements.txt -q")
    if result.returncode != 0:
        print(f"  [WARN] {result.stderr.strip()[:200]}")

    print(f"  [OK] Dependencies installed")
    return True


# ── Step 2: Client Config from Secret Manager ───────────────────────

def setup_client_config():
    header("Step 2: OAuth Client Config (from Secret Manager)")

    if CLIENT_CONFIG_FILE.exists():
        print(f"  [OK] {CLIENT_CONFIG_FILE.name} already exists")
        return True

    client_id = read_secret("gmail-client-id")
    client_secret = read_secret("gmail-client-secret")

    if not client_id or not client_secret:
        print("  [ERROR] Could not read OAuth secrets from Secret Manager")
        print("  Make sure gcloud is authenticated and project is set")
        return False

    config = json.loads(json.dumps(CLIENT_CONFIG_TEMPLATE))  # deep copy
    config["installed"]["client_id"] = client_id
    config["installed"]["client_secret"] = client_secret

    with open(CLIENT_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print(f"  [OK] Created {CLIENT_CONFIG_FILE.name}")
    return True


# ── Step 3: Test Runner Key ──────────────────────────────────────────

def setup_test_runner_key():
    header("Step 3: Test Runner SA Key")

    if TEST_RUNNER_KEY_FILE.exists():
        print(f"  [OK] {TEST_RUNNER_KEY_FILE.name} already exists")
        return True

    print(f"  Downloading key for {TEST_RUNNER_SA}...")
    result = run(
        f'gcloud iam service-accounts keys create "{TEST_RUNNER_KEY_FILE}" '
        f'--iam-account="{TEST_RUNNER_SA}" --project={PROJECT_ID}'
    )

    if result.returncode != 0:
        print(f"  [ERROR] {result.stderr.strip()}")
        return False

    print(f"  [OK] Created {TEST_RUNNER_KEY_FILE.name}")
    return True


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  PEB Service — Developer Setup")
    print("=" * 60)

    # Check gcloud
    result = run("gcloud auth print-access-token")
    if result.returncode != 0:
        print("\n[ERROR] gcloud not authenticated. Run: gcloud auth login")
        return 1

    ok = True
    ok = setup_venv() and ok
    ok = setup_client_config() and ok
    ok = setup_test_runner_key() and ok

    header("Done!")
    if ok:
        activate = ".venv\\Scripts\\activate" if os.name == "nt" else "source .venv/bin/activate"
        print(f"  All set! To get started:\n")
        print(f"    {activate}")
        print(f"    pytest tests/unit/       # fast, no network")
        print(f"    pytest tests/local/      # hits SM, Firestore, OpenAI")
        print()
    else:
        print("  Some steps failed — check the errors above.")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
