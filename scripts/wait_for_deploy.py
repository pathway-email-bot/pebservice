#!/usr/bin/env python3
"""
Polls Cloud Function deployment status until it reaches a new revision.
Usage: python wait_for_deploy.py [expected_revision_number]
If no revision is specified, it just waits for deployment state to become ACTIVE.
"""

import subprocess
import time
import sys

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

def main():
    expected_rev = None
    if len(sys.argv) > 1:
        expected_rev = sys.argv[1]
    
    print("Waiting for Cloud Function deployment...")
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
                return 0
            elif not expected_rev and rev != initial_rev:
                print(f"\n✅ SUCCESS: New revision {rev} is ACTIVE!")
                return 0
            elif not expected_rev and initial_state == "DEPLOYING":
                print(f"\n✅ SUCCESS: Revision {rev} is ACTIVE!")
                return 0
            else:
                print(f"  [{poll_count}] Active but waiting for new revision... ({rev})")
        else:
            print(f"  [{poll_count}] State: {state}, Rev: {rev}")
    
    print("\n❌ TIMEOUT: Deployment did not complete in 5 minutes.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
