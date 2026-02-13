"""Manual E2E test: create attempt, send email, then poll Firestore."""
import os, sys, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import firebase_admin
from firebase_admin import firestore as fb_firestore
from google.cloud import firestore
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
from datetime import datetime

# --- Config ---
PROJECT_ID = 'pathway-email-bot-6543'
TEST_EMAIL = 'michaeltreynolds.test@gmail.com'
BOT_EMAIL = 'pathwayemailbot@gmail.com'
SCENARIO_ID = 'missed_remote_standup'

# --- Init Firebase ---
os.environ.setdefault('GOOGLE_CLOUD_PROJECT', PROJECT_ID)
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={'projectId': PROJECT_ID})

db = firestore.Client(database='pathway')

# --- Init Gmail for test account ---
with open('client_config.secret.json') as f:
    cfg = json.load(f)['installed']
with open('token.test.secret.json') as f:
    tok = json.load(f)

creds = Credentials(
    None,
    refresh_token=tok['refresh_token'],
    token_uri='https://oauth2.googleapis.com/token',
    client_id=cfg['client_id'],
    client_secret=cfg['client_secret']
)
gmail = build('gmail', 'v1', credentials=creds)
print("[OK] Gmail service initialized")

# --- Step 1: Create Firestore attempt ---
attempt_ref = db.collection('users').document(TEST_EMAIL).collection('attempts').document()
attempt_ref.set({
    'scenarioId': SCENARIO_ID,
    'status': 'pending',
    'createdAt': fb_firestore.SERVER_TIMESTAMP,
    'startedAt': fb_firestore.SERVER_TIMESTAMP,
})
attempt_id = attempt_ref.id
print(f"[OK] Created attempt: {attempt_id}")
print(f"     Path: users/{TEST_EMAIL}/attempts/{attempt_id}")

# Set active scenario on user doc (matches what firestore_client.create_attempt does)
user_ref = db.collection('users').document(TEST_EMAIL)
user_ref.set({
    'activeScenarioId': SCENARIO_ID,
    'activeAttemptId': attempt_id,
}, merge=True)
print(f"[OK] Set activeScenarioId={SCENARIO_ID}, activeAttemptId={attempt_id} on user doc")

# --- Step 2: Send email ---
body_text = (
    "Hi team,\n\n"
    "I apologize for missing the standup this morning. I overslept due to a late night "
    "debugging a production issue. Here's my update:\n\n"
    "Yesterday: Completed the API endpoint refactoring and submitted PR #142 for review.\n"
    "Today: Planning to finish the database migration script and review Sarah's PR.\n"
    "Blockers: Need access to the staging database credentials - waiting on DevOps.\n\n"
    "I'll make sure to set an extra alarm going forward. Sorry again for the inconvenience.\n\n"
    "Best regards"
)

subject = f"Re: Missed Remote Standup - {SCENARIO_ID}"
msg = MIMEText(body_text)
msg['to'] = BOT_EMAIL
msg['from'] = TEST_EMAIL
msg['subject'] = subject
raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

sent = gmail.users().messages().send(userId='me', body={'raw': raw}).execute()
print(f"[OK] Email sent! Message ID: {sent['id']}")
print(f"     Subject: {subject}")

# --- Step 3: Poll Firestore for grading ---
print(f"\n[...] Waiting for grading (polling Firestore every 5s, max 120s)...")
start = time.time()
while time.time() - start < 120:
    doc = attempt_ref.get()
    d = doc.to_dict()
    status = d.get('status')
    score = d.get('score')
    elapsed = int(time.time() - start)
    
    if score is not None or status == 'graded':
        print(f"\n[PASS] Graded after {elapsed}s!")
        print(f"  Status:   {status}")
        print(f"  Score:    {score}")
        print(f"  Feedback: {str(d.get('feedback', ''))[:200]}")
        sys.exit(0)
    
    print(f"  {elapsed}s - status={status}, score={score}", end='\r')
    time.sleep(5)

print(f"\n[FAIL] Timeout after 120s - no grading received")
print(f"  Final status: {d.get('status')}")
sys.exit(1)
