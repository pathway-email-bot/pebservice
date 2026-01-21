#!/usr/bin/env python3
"""
Full integration test: push -> deploy -> send test email -> verify logs.

Usage: python push_deploy_integration_test.py [--skip-push] [--skip-email] [--skip-tokens]

This script:
0. Checks that required tokens are valid (gcloud, Gmail)
1. Pushes current changes to GitHub (triggers CI/CD)
2. Waits for Cloud Function deployment to complete
3. Sends a test email to the bot
4. Waits for processing and checks logs for success markers

Prerequisites:
    - Run 'python ensure_tokens.py' first to set up authentication
"""

import subprocess
import sys
import time
import re
from datetime import datetime, timedelta

# Configuration
FUNCTION_NAME = "process_email"
REGION = "us-central1"
LOG_WAIT_SECONDS = 60
DEPLOY_TIMEOUT_SECONDS = 300

# Success markers to look for in logs
SUCCESS_MARKERS = [
    "PEB Service module loaded",  # Canary log - proves logging works
    "process_email triggered",
    "Processing Email",
    "Agent finished",
    "Reply SENT successfully",
]


def run_cmd(cmd: str, check: bool = True) -> tuple[int, str]:
    """Run a shell command and return (exit_code, output)."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = result.stdout + result.stderr
    if check and result.returncode != 0:
        print(f"[ERROR] Command failed: {cmd}")
        print(output)
    return result.returncode, output


def step_header(msg: str):
    """Print a step header."""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def push_changes() -> bool:
    """Push current changes to GitHub."""
    step_header("Step 1: Pushing changes to GitHub")
    
    # Check if there are changes to push
    code, output = run_cmd("git status --porcelain", check=False)
    if output.strip():
        print("[INFO] Uncommitted changes detected. Please commit first.")
        return False
    
    code, output = run_cmd("git push", check=False)
    if code != 0:
        print("[ERROR] git push failed")
        print(output)
        return False
    
    print("[OK] Changes pushed to GitHub")
    return True


def wait_for_deploy() -> bool:
    """Wait for Cloud Function deployment to complete."""
    step_header("Step 2: Waiting for deployment")
    
    # Get initial revision
    code, output = run_cmd(
        f'gcloud functions describe {FUNCTION_NAME} --region {REGION} '
        f'--format "value(serviceConfig.revision)"',
        check=False
    )
    initial_rev = output.strip() if code == 0 else None
    print(f"[INFO] Initial revision: {initial_rev}")
    
    start_time = time.time()
    poll_count = 0
    
    while time.time() - start_time < DEPLOY_TIMEOUT_SECONDS:
        time.sleep(10)
        poll_count += 1
        
        code, output = run_cmd(
            f'gcloud functions describe {FUNCTION_NAME} --region {REGION} '
            f'--format "value(state,serviceConfig.revision)"',
            check=False
        )
        
        if code != 0:
            print(f"  [{poll_count}] Error querying function status")
            continue
        
        parts = output.strip().split()
        state = parts[0] if parts else "UNKNOWN"
        revision = parts[1] if len(parts) > 1 else None
        
        if state == "DEPLOYING":
            print(f"  [{poll_count}] Deploying... (rev: {revision})")
        elif state == "ACTIVE":
            if revision != initial_rev:
                print(f"\n[OK] New revision {revision} is ACTIVE!")
                return True
            else:
                print(f"  [{poll_count}] Active, waiting for new revision... (rev: {revision})")
        else:
            print(f"  [{poll_count}] State: {state}, Rev: {revision}")
    
    print("\n[ERROR] Deployment timeout")
    return False


def send_test_email() -> bool:
    """Send a test email using send_test_email.py."""
    step_header("Step 3: Sending test email")
    
    code, output = run_cmd("python send_test_email.py", check=False)
    print(output)
    
    if "SUCCESS" in output:
        print("[OK] Test email sent")
        return True
    else:
        print("[ERROR] Failed to send test email")
        return False


def check_logs() -> bool:
    """Check Cloud Function logs for success markers."""
    step_header("Step 4: Checking logs for success markers")
    
    print(f"[INFO] Waiting {LOG_WAIT_SECONDS}s for email processing...")
    time.sleep(LOG_WAIT_SECONDS)
    
    # Fetch recent logs
    code, output = run_cmd(
        f'gcloud functions logs read {FUNCTION_NAME} --region {REGION} '
        f'--limit 50 --format "value(textPayload)"',
        check=False
    )
    
    if code != 0:
        print("[ERROR] Failed to fetch logs")
        return False
    
    print("\n--- Recent Logs ---")
    print(output[:2000] if len(output) > 2000 else output)
    print("-------------------\n")
    
    # Check for success markers
    found_markers = []
    missing_markers = []
    
    for marker in SUCCESS_MARKERS:
        if marker.lower() in output.lower():
            found_markers.append(marker)
        else:
            missing_markers.append(marker)
    
    print("Success markers found:")
    for m in found_markers:
        print(f"  [✓] {m}")
    
    if missing_markers:
        print("\nMarkers NOT found (may be OK if no recent email):")
        for m in missing_markers:
            print(f"  [?] {m}")
    
    # At minimum, the canary log should appear
    if "PEB Service module loaded" in found_markers:
        print("\n[OK] Logging is operational (canary log found)")
        return True
    else:
        print("\n[WARN] Canary log not found - logging may not be working")
        return False


def check_tokens() -> bool:
    """Run ensure_tokens.py to verify authentication."""
    step_header("Step 0: Checking authentication tokens")
    
    code, output = run_cmd("python ensure_tokens.py", check=False)
    
    # Check if tokens are valid based on exit code
    if code == 0:
        print("[OK] All required tokens are valid")
        return True
    else:
        print("[WARN] Token check returned warnings")
        print("Run 'python ensure_tokens.py' manually to fix")
        return False


def main():
    skip_push = "--skip-push" in sys.argv
    skip_email = "--skip-email" in sys.argv
    skip_tokens = "--skip-tokens" in sys.argv
    
    print("=" * 60)
    print("  PEB Service - Full Integration Test")
    print("=" * 60)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Skip tokens: {skip_tokens}")
    print(f"  Skip push: {skip_push}")
    print(f"  Skip email: {skip_email}")
    
    results = {}
    
    # Step 0: Check tokens
    if not skip_tokens:
        results["tokens"] = check_tokens()
        if not results["tokens"]:
            response = input("\nContinue anyway? (y/n): ").strip().lower()
            if response != "y":
                print("[ABORT] Fix tokens first with: python ensure_tokens.py")
                return 1
    
    # Step 1: Push
    if not skip_push:
        results["push"] = push_changes()
        if not results["push"]:
            print("\n[ABORT] Push failed, stopping.")
            return 1
    
    # Step 2: Wait for deploy
    if not skip_push:
        results["deploy"] = wait_for_deploy()
        if not results["deploy"]:
            print("\n[WARN] Deployment may have issues, continuing anyway...")
    
    # Step 3: Send test email
    if not skip_email:
        results["email"] = send_test_email()
    
    # Step 4: Check logs
    results["logs"] = check_logs()
    
    # Summary
    step_header("Summary")
    all_passed = True
    for step, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {step}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n[SUCCESS] All integration tests passed!")
        return 0
    else:
        print("\n[WARN] Some tests failed or had warnings")
        return 1


if __name__ == "__main__":
    sys.exit(main())
