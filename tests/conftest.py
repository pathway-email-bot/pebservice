"""
Shared test configuration — auto-discovers GCP credentials.

Credential resolution (same logic for CI and local):
  1. If GOOGLE_APPLICATION_CREDENTIALS is already set AND the file exists, use it.
  2. Otherwise, look for test-runner-key.secret.json in the repo root.
  3. If neither works, fail with a clear message.

This means:
  - CI: google-github-actions/auth sets GOOGLE_APPLICATION_CREDENTIALS → path 1.
  - Local: test-runner-key.secret.json exists in repo root → path 2.
  - No manual env var setup needed in either case.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_KEY = REPO_ROOT / "test-runner-key.secret.json"


def pytest_configure(config):
    """Auto-set GOOGLE_APPLICATION_CREDENTIALS before any test runs."""
    current = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    # Path 1: env var already set and file exists — trust it (CI flow)
    if current and os.path.isfile(current):
        return

    # Path 2: auto-discover the test runner key in repo root
    if TEST_KEY.is_file():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(TEST_KEY)
        return

    # Path 3: nothing found — let tests fail with a clear message
    import warnings
    warnings.warn(
        "\n\n"
        "⚠️  No GCP credentials found for integration tests!\n"
        "    Option A: Place test-runner-key.secret.json in the repo root\n"
        "    Option B: Set GOOGLE_APPLICATION_CREDENTIALS env var\n"
        "    See service_notes.md → 'Service Accounts & IAM' for setup.\n"
    )
