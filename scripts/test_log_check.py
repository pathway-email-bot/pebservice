#!/usr/bin/env python3
"""Test the check_cloud_function_logs function."""

import subprocess

TEST_EMAIL = "michaeltreynolds.test@gmail.com"

class Colors:
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    ENDC = '\033[0m'

def print_info(msg: str):
    print(f"{Colors.OKCYAN}ℹ{Colors.ENDC} {msg}")

def check_cloud_function_logs(attempt_id: str = None):
    """Check recent process_email Cloud Function logs."""
    try:
        result = subprocess.run(
            'gcloud functions logs read process_email --gen2 --region=us-central1 --limit=10 --format=value(log)',
            capture_output=True,
            text=True,
            timeout=10,
            shell=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            logs = result.stdout.strip().split('\n')
            
            print_info(f"Fetched {len(logs)} log lines")
            
            # If we have an attempt_id, look for it specifically
            if attempt_id:
                matching = [log for log in logs if attempt_id in log]
                if matching:
                    print_info(f"Logs for attempt {attempt_id[:8]}:")
                    for log in matching[-5:]:
                        print(f"    {log[:150]}")
                    return
                else:
                    print_info(f"No logs found for attempt {attempt_id[:8]}")
            
            # Show recent relevant logs
            relevant = [log for log in logs[-10:] if any(keyword in log.lower() for keyword in 
                       ['error', 'processing email', 'grading', 'updated firestore', 'score=',
                        TEST_EMAIL.lower(), 'exception', 'found active scenario'])]
            if relevant:
                print_info("Recent relevant logs:")
                for log in relevant[-5:]:
                    print(f"    {log[:150]}")
            else:
                print_info("No relevant logs found in last 10 entries")
                print_info("Showing all recent logs:")
                for log in logs[-5:]:
                    print(f"    {log[:150]}")
        else:
            print_info(f"Could not fetch logs (exit code: {result.returncode})")
            if result.stderr:
                print_info(f"Error: {result.stderr}")
    except Exception as e:
        print_info(f"Log check failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\nTesting check_cloud_function_logs()...")
    print("=" * 60)
    
    # Test without attempt_id
    print("\n1. General log check (no attempt_id):")
    check_cloud_function_logs()
    
    # Test with fake attempt_id (should show no matches)
    print("\n\n2. Log check with fake attempt_id:")
    check_cloud_function_logs("fake12345678")
    
    print("\n" + "=" * 60)
    print("Test complete!")
