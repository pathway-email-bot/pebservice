#!/usr/bin/env python3
"""
End-to-End Test Script for INITIATE Scenario Flow

Tests the complete flow:
1. Create Firestore attempt (simulates "Start" button)
2. Send email from test account to pathwayemailbot@gmail.com
3. Wait for process_email to run and grade the email
4. Verify Firestore is updated with grading results

Usage:
    python scripts/test_initiate_flow.py [--scenario SCENARIO_ID] [--no-save-logs]

Logs are saved to test_logs/<timestamp>_<attempt_id>.log by default.

Requirements:
    - token.test.secret.json (run: python scripts/get_token.py --test)
    - Service account credentials in GOOGLE_APPLICATION_CREDENTIALS
    - Firebase project configured
"""

import os
import sys
import json
import time
import base64
import shutil
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import firebase_admin
from firebase_admin import credentials as firebase_credentials
from google.cloud import firestore

# Configuration
TEST_EMAIL = "michaeltreynolds.test@gmail.com"
BOT_EMAIL = "pathwayemailbot@gmail.com"
DEFAULT_SCENARIO = "missed_remote_standup"
TOKEN_FILE = "token.test.secret.json"
LOG_DIR = Path("test_logs")


class TeeLogger:
    """Duplicates writes to both a stream and a log file."""
    def __init__(self, stream, log_file):
        self.stream = stream
        self.log_file = log_file

    def write(self, data):
        self.stream.write(data)
        self.log_file.write(data)
        self.log_file.flush()

    def flush(self):
        self.stream.flush()
        self.log_file.flush()

    def fileno(self):
        return self.stream.fileno()

# Colors for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_step(step_num: int, msg: str):
    print(f"\n{Colors.BOLD}[Step {step_num}]{Colors.ENDC} {msg}")


def print_success(msg: str):
    print(f"{Colors.OKGREEN}✓{Colors.ENDC} {msg}")


def print_error(msg: str):
    print(f"{Colors.FAIL}✗{Colors.ENDC} {msg}")


def print_info(msg: str):
    print(f"{Colors.OKCYAN}ℹ{Colors.ENDC} {msg}")


def init_firebase():
    """Initialize Firebase Admin SDK."""
    try:
        firebase_admin.get_app()
        print_info("Firebase already initialized")
    except ValueError:
        # Try GOOGLE_APPLICATION_CREDENTIALS first
        cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if cred_path:
            cred = firebase_credentials.Certificate(cred_path)
            print_info(f"Using service account: {cred_path}")
        else:
            # Fall back to application default credentials
            try:
                cred = firebase_credentials.ApplicationDefault()
                print_info("Using application default credentials")
            except Exception as e:
                print_error("No credentials found")
                print_info("Run: gcloud auth application-default login")
                print_info("Or set GOOGLE_APPLICATION_CREDENTIALS to service account key path")
                sys.exit(1)
        
        firebase_admin.initialize_app(cred)
        print_success("Firebase initialized")
    
    # Use google.cloud.firestore.Client directly (same as service code)
    return firestore.Client(database='pathway')


def get_gmail_service_for_test() -> 'googleapiclient.discovery.Resource':
    """Build Gmail service for test account using stored token."""
    if not Path(TOKEN_FILE).exists():
        print_error(f"{TOKEN_FILE} not found")
        print_info("Run: python scripts/get_token.py --test")
        sys.exit(1)
    
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    
    refresh_token = token_data['refresh_token']
    
    # Get OAuth config from client_config
    with open('client_config.secret.json') as f:
        client_config = json.load(f)
        client_id = client_config['installed']['client_id']
        client_secret = client_config['installed']['client_secret']
    
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    
    return build('gmail', 'v1', credentials=creds)


def create_firestore_attempt(db: firestore.Client, scenario_id: str) -> str:
    """Create a Firestore attempt document (simulates Start button)."""
    print_step(1, f"Creating Firestore attempt for scenario: {scenario_id}")
    
    attempt_data = {
        "scenarioId": scenario_id,
        "status": "active",
        "createdAt": firestore.SERVER_TIMESTAMP,
        "score": None,
        "maxScore": None,
        "feedback": None,
    }
    
    # Create attempt document
    user_ref = db.collection('users').document(TEST_EMAIL)
    attempt_ref = user_ref.collection('attempts').document()
    attempt_ref.set(attempt_data)
    
    attempt_id = attempt_ref.id
    
    # Set as active scenario
    user_ref.set({
        "activeScenario": {
            "scenarioId": scenario_id,
            "attemptId": attempt_id,
            "startedAt": firestore.SERVER_TIMESTAMP,
        }
    }, merge=True)
    
    print_success(f"Created attempt: {attempt_id}")
    print_info(f"Firestore path: users/{TEST_EMAIL}/attempts/{attempt_id}")
    
    return attempt_id


def send_test_email(gmail_service: 'googleapiclient.discovery.Resource', scenario_id: str):
    """Send test email from test account to bot."""
    print_step(2, f"Sending test email from {TEST_EMAIL} to {BOT_EMAIL}")
    
    # Compose a professional email based on scenario
    subject = f"Re: Missed Remote Standup - {scenario_id}"
    body = f"""Hi,

I apologize for missing today's standup meeting. I had an unexpected technical issue with my internet connection this morning.

I wanted to provide a quick update on my progress:
- Completed the database migration tasks
- Currently working on the API endpoint updates
- Planning to finish the unit tests by end of day

Is there a time later today when I could catch up with you on what I missed?

Thanks for understanding.

Best regards,
Test Student"""
    
    # Build MIME message
    message = MIMEText(body)
    message['To'] = BOT_EMAIL
    message['From'] = TEST_EMAIL
    message['Subject'] = subject
    
    # Encode for Gmail API
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    # Send
    try:
        sent = gmail_service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        print_success(f"Email sent! Message ID: {sent['id']}")
        print_info(f"Subject: {subject}")
        print_info(f"Body length: {len(body)} chars")
        
        return sent['id']
    
    except Exception as e:
        print_error(f"Failed to send email: {e}")
        sys.exit(1)


def wait_for_grading(db: firestore.Client, attempt_id: str, timeout: int = 60) -> bool:
    """Wait for process_email to grade and update Firestore."""
    print_step(3, f"Waiting for grading (timeout: {timeout}s)")
    
    user_ref = db.collection('users').document(TEST_EMAIL)
    attempt_ref = user_ref.collection('attempts').document(attempt_id)
    
    start_time = time.time()
    last_log_check = 0
    
    while time.time() - start_time < timeout:
        # Check attempt document
        doc = attempt_ref.get()
        if doc.exists:
            data = doc.to_dict()
            score = data.get('score')
            
            if score is not None:
                print_success("Grading complete!")
                print_info(f"Score: {score}/{data.get('maxScore', '?')}")
                print_info(f"Feedback: {data.get('feedback', 'N/A')[:100]}...")
                return True
        
        # Check Cloud Function logs every 10 seconds
        elapsed = int(time.time() - start_time)
        if elapsed - last_log_check >= 10:
            print_info(f"\nChecking process_email logs...")
            check_cloud_function_logs(attempt_id)
            last_log_check = elapsed
        
        # Progress indicator
        print(f"\r  Waiting... {elapsed}s ", end='', flush=True)
        time.sleep(3)
    
    print()
    print_error(f"Timeout after {timeout}s - no grading received")
    print_info("Checking logs one more time...")
    check_cloud_function_logs(attempt_id)
    return False


def check_cloud_function_logs(attempt_id: str = None):
    """Check recent process_email Cloud Function logs."""
    import subprocess
    from datetime import datetime, timedelta, timezone
    
    try:
        # Get logs from last 10 seconds only to see current activity
        time_filter = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        result = subprocess.run(
            f'gcloud functions logs read process_email --gen2 --region=us-central1 --limit=30 --format=value(log) --filter="timestamp>=\\"{time_filter}\\""',
            capture_output=True,
            text=True,
            timeout=10,
            shell=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            logs = result.stdout.strip().split('\n')
            
            # If we have an attempt_id, look for it specifically
            if attempt_id:
                matching = [log for log in logs if attempt_id in log]
                if matching:
                    print_info(f"Logs for attempt {attempt_id[:8]}:")
                    for log in matching[-5:]:
                        print(f"    {log[:150]}")
                    return
            
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
        else:
            print_info("Could not fetch logs")
    except Exception as e:
        print_info(f"Log check failed: {e}")


def verify_email_sent(gmail_service: 'googleapiclient.discovery.Resource') -> bool:
    """Check if bot replied to our email."""
    print_step(4, "Checking for reply from bot")
    
    try:
        # Search for emails from bot
        results = gmail_service.users().messages().list(
            userId='me',
            q=f'from:{BOT_EMAIL}',
            maxResults=5
        ).execute()
        
        messages = results.get('messages', [])
        
        if messages:
            # Get most recent message
            msg_id = messages[0]['id']
            msg = gmail_service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'N/A')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'N/A')
            
            print_success(f"Found reply from bot!")
            print_info(f"Subject: {subject}")
            print_info(f"Date: {date}")
            
            return True
        else:
            print_error("No reply from bot found yet")
            return False
    
    except Exception as e:
        print_error(f"Error checking inbox: {e}")
        return False


def main():
    # Parse args
    scenario_id = DEFAULT_SCENARIO
    save_logs = "--no-save-logs" not in sys.argv
    if '--scenario' in sys.argv:
        idx = sys.argv.index('--scenario')
        if idx + 1 < len(sys.argv):
            scenario_id = sys.argv[idx + 1]
    
    # Set up log capture
    log_file = None
    log_path = None
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    if save_logs:
        LOG_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Start with timestamp-only name; rename after we have attempt_id
        log_path = LOG_DIR / f"{timestamp}_pending.log"
        log_file = open(log_path, 'w', encoding='utf-8')
        sys.stdout = TeeLogger(original_stdout, log_file)
        sys.stderr = TeeLogger(original_stderr, log_file)
    
    print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}  PEB End-to-End Test: INITIATE Flow{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"\n  Test Email: {TEST_EMAIL}")
    print(f"  Bot Email: {BOT_EMAIL}")
    print(f"  Scenario: {scenario_id}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if log_path:
        print(f"  Log file: {log_path}")
    
    # Initialize services
    print_step(0, "Initializing services")
    db = init_firebase()
    gmail_service = get_gmail_service_for_test()
    print_success("Services ready")
    
    # Run test flow
    try:
        # Step 1: Create Firestore attempt
        attempt_id = create_firestore_attempt(db, scenario_id)
        
        # Rename log file to include attempt_id
        if log_path and log_path.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_log_path = LOG_DIR / f"{timestamp}_{attempt_id[:8]}.log"
            log_file.flush()
            # Close, rename, reopen
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            log_file.close()
            shutil.move(str(log_path), str(new_log_path))
            log_path = new_log_path
            log_file = open(log_path, 'a', encoding='utf-8')
            sys.stdout = TeeLogger(original_stdout, log_file)
            sys.stderr = TeeLogger(original_stderr, log_file)
            print_info(f"Log file renamed to: {log_path}")
        
        # Step 2: Send email
        message_id = send_test_email(gmail_service, scenario_id)
        
        # Step 3: Wait for grading
        success = wait_for_grading(db, attempt_id, timeout=60)
        
        if success:
            # Step 4: Verify reply
            time.sleep(5)  # Give email a moment to arrive
            verify_email_sent(gmail_service)
        
        # Final result
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        if success:
            print(f"{Colors.OKGREEN}{Colors.BOLD}  TEST PASSED ✓{Colors.ENDC}")
            print(f"{Colors.OKGREEN}{'='*60}{Colors.ENDC}")
            if log_path:
                print_info(f"Full log saved to: {log_path}")
            return 0
        else:
            print(f"{Colors.FAIL}{Colors.BOLD}  TEST FAILED ✗{Colors.ENDC}")
            print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}")
            print_info("Check Cloud Function logs: gcloud functions logs read process_email --gen2 --region=us-central1 --limit=50")
            if log_path:
                print_info(f"Full log saved to: {log_path}")
            return 1
    
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Test interrupted by user{Colors.ENDC}")
        return 1
    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Restore stdout/stderr and close log file
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if log_file:
            log_file.close()


if __name__ == "__main__":
    sys.exit(main())
