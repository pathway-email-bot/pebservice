#!/usr/bin/env python3
"""
Waits for GitHub Actions deployment to complete, then monitors Cloud Function status.
Usage: python wait_for_deploy.py [expected_revision_number]
If no revision is specified, it just waits for deployment state to become ACTIVE.
"""

import subprocess
import time
import sys
import json

def get_latest_workflow_run():
    """Get the latest deploy workflow run and its status."""
    result = subprocess.run(
        'gh run list --workflow=deploy.yaml --limit=1 --json status,conclusion,headBranch --jq ".[0]"',
        capture_output=True,
        text=True,
        shell=True
    )
    if result.returncode != 0:
        return None
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

def wait_for_github_action():
    """Wait for the latest GitHub Actions deploy workflow to complete."""
    print("Checking GitHub Actions deployment status...")
    
    poll_count = 0
    max_polls = 120  # 10 minutes max (5 sec intervals)
    
    while poll_count < max_polls:
        run = get_latest_workflow_run()
        
        if run is None:
            print("  [!] Could not fetch GitHub Actions status. Continuing anyway...")
            return True
        
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion", "")
        
        if status == "completed":
            if conclusion == "success":
                print(f"✅ GitHub Actions deployment completed successfully")
                return True
            else:
                print(f"❌ GitHub Actions deployment failed with conclusion: {conclusion}")
                return False
        else:
            poll_count += 1
            print(f"  [{poll_count}] GitHub Actions still running... (status: {status})")
            time.sleep(5)
    
    print("❌ TIMEOUT: GitHub Actions did not complete in 10 minutes")
    return False

def get_current_status():
    """Get current function state and revision."""
    result = subprocess.run(
        'gcloud functions describe process_email --region us-central1 --format "value(state,serviceConfig.revision)"',
        capture_output=True,
        text=True,
        shell=True
    )
    if result.returncode != 0:
        return None, None
    
    parts = result.stdout.strip().split()
    if len(parts) >= 2:
        return parts[0], parts[1]  # state, revision
    elif len(parts) == 1:
        return parts[0], None
    return None, None

def wait_for_cloud_function(expected_rev=None):
    """Wait for Cloud Function to be deployed and active."""
    print("\nWaiting for Cloud Function deployment...")
    initial_state, initial_rev = get_current_status()
    print(f"Initial: {initial_state} - {initial_rev}")
    
    poll_count = 0
    max_polls = 60  # 5 minutes max (5 sec intervals)
    
    while poll_count < max_polls:
        time.sleep(5)
        poll_count += 1
        
        state, rev = get_current_status()
        
        if state == "DEPLOYING":
            print(f"  [{poll_count}] Deploying... ({rev})")
            continue
        
        if state == "ACTIVE":
            if expected_rev and rev == expected_rev:
                print(f"\n✅ SUCCESS: Revision {rev} is ACTIVE!")
                return True
            elif not expected_rev and rev != initial_rev:
                print(f"\n✅ SUCCESS: New revision {rev} is ACTIVE!")
                return True
            elif not expected_rev and initial_state == "DEPLOYING":
                print(f"\n✅ SUCCESS: Revision {rev} is ACTIVE!")
                return True
            else:
                print(f"  [{poll_count}] Active but waiting for new revision... ({rev})")
        else:
            print(f"  [{poll_count}] State: {state}, Rev: {rev}")
    
    print("\n❌ TIMEOUT: Cloud Function deployment did not complete in 5 minutes.")
    return False

def main():
    expected_rev = None
    if len(sys.argv) > 1:
        expected_rev = sys.argv[1]
    
    print("=" * 60)
    print("PEB Service - Deployment Monitor")
    print("=" * 60)
    
    # Step 1: Wait for GitHub Actions
    if not wait_for_github_action():
        return 1
    
    # Step 2: Wait for Cloud Function to update
    if not wait_for_cloud_function(expected_rev):
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
