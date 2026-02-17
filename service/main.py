"""
Pathway Email Bot (PEB) - Cloud Functions Main Entry Point

This file contains TWO separate Google Cloud Functions that share the same codebase:

1. process_email (Cloud Event / Pub/Sub trigger)
   - Triggered by Gmail push notifications when student sends email
   - Fetches email, grades it using EmailAgent + rubric, saves to Firestore, sends reply
   - Deployed as: gcloud functions deploy process_email --trigger-topic=gmail-notifications

2. start_scenario (HTTP trigger)
   - Called by portal frontend to start a scenario (INITIATE or REPLY)
   - Validates Firebase auth, creates Firestore attempt, ensures Gmail watch
   - For REPLY scenarios: also sends starter email via Gmail API
   - Deployed as: gcloud functions deploy start_scenario --trigger-http

Both functions deploy from this same source directory (./service) and share:
  - email_agent/ (scenario loading, grading logic, email agent)
  - firestore_client.py (shared utilities)
  - Scenario and rubric JSON files

This architecture is required by Cloud Functions deployment model, which needs a main.py
file at the root of the source directory.
"""

import base64
import json
import os
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email.mime.text import MIMEText

import functions_framework
from flask import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.cloud import secretmanager
from google.cloud import firestore as firestore_lib
import firebase_admin
from firebase_admin import auth as firebase_auth

from .email_agent.scenario_loader import load_scenario
from .email_agent.rubric_loader import load_rubric
from .email_agent.email_agent import EmailAgent, EmailMessage
from .logging_utils import log_function, setup_cloud_logging

# Setup Logging — uses structured JSON on GCP, plain text locally
setup_cloud_logging()
logger = logging.getLogger(__name__)

# Strip whitespace from secrets injected via --set-secrets (can have trailing \r\n)
if os.environ.get('OPENAI_API_KEY'):
    os.environ['OPENAI_API_KEY'] = os.environ['OPENAI_API_KEY'].strip()

# Initialize Firebase Admin (only once, shared by both functions)
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

# Constants - Path resolution
# Note: email_agent/ directory structure is preserved in Cloud Functions deployment
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RUBRIC_PATH = BASE_DIR / "email_agent/rubrics/default.json"
BOT_EMAIL = "pathwayemailbot@gmail.com"

# Canary log to verify logging is working in Cloud Functions
logger.info("PEB Service module loaded. Logging is operational.")

@functions_framework.cloud_event
@log_function
def process_email(cloud_event):
    """
    Triggered from a message on a Cloud Pub/Sub topic.
    The message usually comes from Gmail push notifications.
    """
    
    # 1. Decode the Pub/Sub message
    data = cloud_event.data
    pubsub_message = data.get("message", {})

    
    if "data" in pubsub_message:
        message_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")

        
        try:
            notification = json.loads(message_data)
            email_address = notification.get("emailAddress")
            history_id = notification.get("historyId")
            
            if not history_id:
                logger.warning("No historyId found in notification")
                return "OK"
                
            logger.info(f"Processing notification for {email_address}, historyId: {history_id}")
            
            # 2. Initialize Gmail Service
            service = get_gmail_service()
            if not service:
                logger.error("Failed to initialize Gmail service")
                return "OK"

            # 3. List history to find the message ID
            try:
                logger.debug(f"Fetching history starting from historyId={history_id}")
                history = service.users().history().list(userId='me', startHistoryId=history_id).execute()
                changes = history.get('history', [])
                
                if not changes:
                    logger.debug("No history changes found. Attempting fallback to latest message.")
                    # Fallback: Get the most recent message
                    try:
                        response = service.users().messages().list(userId='me', maxResults=1).execute()
                        messages = response.get('messages', [])
                        if messages:
                            latest_msg_id = messages[0]['id']
                            logger.debug(f"Fallback found message ID: {latest_msg_id}")
                            msg = service.users().messages().get(userId='me', id=latest_msg_id, format='full').execute()
                            process_single_message(service, msg)
                            return "OK"
                        else:
                            logger.debug("Fallback found no messages either")
                            return "OK"
                    except Exception as fb_e:
                        logger.error(f"Fallback failed: {fb_e}", exc_info=True)
                        return "OK"

                logger.debug(f"Found {len(changes)} history changes")

                found_message = False
                for change in changes:
                    messages_added = change.get('messagesAdded', [])
                    for record in messages_added:
                        message_id = record.get('message', {}).get('id')
                        if message_id:
                             logger.debug(f"Processing added message ID: {message_id}")
                             # 4. Get full message details
                             msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
                             process_single_message(service, msg)
                             found_message = True
                
                if not found_message:
                    logger.debug("No 'messagesAdded' events found in history")

            except Exception as e:
                logger.error(f"Error fetching history: {e}", exc_info=True)
            
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from Pub/Sub message")
    else:
        logger.warning("No data in Pub/Sub message")

    return "OK"

def get_header(headers, name, default=""):
    """Case-insensitive header lookup."""
    name_lower = name.lower()
    return next((h['value'] for h in headers if h['name'].lower() == name_lower), default)

@log_function
def process_single_message(service, msg):
    """Parses email content and decides on action."""
    try:
        from .firestore_client import get_active_scenario, update_attempt_graded
        
        headers = msg.get('payload', {}).get('headers', [])
        subject = get_header(headers, 'Subject', 'No Subject')
        sender = get_header(headers, 'From', 'Unknown')
        
        # Extract sender email from "Name <email@example.com>" format
        sender_email = sender
        if '<' in sender and '>' in sender:
            sender_email = sender.split('<')[1].split('>')[0].strip()
        
        # Extract Body (Text/Plain)
        body = "No Body"
        parts = msg.get('payload', {}).get('parts', [])
        if not parts:
            # Sometimes payload body has data directly if no parts
            data = msg.get('payload', {}).get('body', {}).get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')
        else:
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        
        logger.info(f"Email from: {sender_email} | Subject: {subject}")
        
        # Guard: Don't reply to self or bots to avoid loops
        if "google" in sender.lower() or "bot" in sender.lower() or "noreply" in sender.lower():
             logger.info(f"Skipping auto-reply for likely bot/self: {sender}")
             return

        # Get active scenario from Firestore

        active_scenario = get_active_scenario(sender_email)
        
        if not active_scenario:
            logger.warning(f"No active scenario found for {sender_email}")

            
            # Send redirect response
            redirect_message = (
                "Thanks for your email! To practice email scenarios, please visit the student portal "
                "and click 'Start' on a scenario first. Then reply to the scenario email you receive.\n\n"
                "Portal: https://pathway-email-bot.github.io/pebservice/"
            )
            send_reply(service, msg, redirect_message)
            return
        
        scenario_id, attempt_id = active_scenario
        logger.info(f"Found active scenario: {scenario_id} (attempt: {attempt_id})")
        
        # Load scenario and rubric

        scenario = load_scenario(scenario_id)
        rubric = load_rubric(DEFAULT_RUBRIC_PATH)
        
        # Fetch OpenAI API key from Secret Manager
        try:
            project_id = os.environ.get('GCP_PROJECT') or os.environ.get('GOOGLE_CLOUD_PROJECT')
            if not project_id:
                import requests
                metadata_server = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
                headers = {"Metadata-Flavor": "Google"}
                project_id = requests.get(metadata_server, headers=headers).text
            
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{project_id}/secrets/openai-api-key/versions/latest"
            response = client.access_secret_version(request={"name": name})
            api_key = response.payload.data.decode('UTF-8').strip()

        except Exception as e:
            logger.error(f"Failed to fetch OpenAI API key from Secret Manager: {e}")
            api_key = os.environ.get("OPENAI_API_KEY")  # Fallback to env var
        
        if not api_key:
            logger.error("Missing OPENAI_API_KEY")
            return


        agent = EmailAgent(
            model="gpt-4o",
            temperature=0.2,
            scenario=scenario,
            api_key=api_key
        )
        
        # Create Student Email Object
        student_email = EmailMessage(
            sender=sender,
            subject=subject,
            body=body
        )
        
        # Process interaction

        prior_thread = agent.build_starter_thread() 
        
        result = agent.evaluate_and_respond(
            prior_thread=prior_thread,
            student_email=student_email,
            rubric=rubric.items
        )
        


        # Update Firestore with grading results
        if result.grading:
            # Build rubric breakdown for Firestore storage
            rubric_scores = [
                {
                    "name": s.name,
                    "score": s.score,
                    "maxScore": s.max_score,
                    "justification": s.justification,
                }
                for s in result.grading.scores
            ]
            update_attempt_graded(
                email=sender_email,
                attempt_id=attempt_id,
                score=result.grading.total_score,
                max_score=result.grading.max_total_score,
                feedback=result.grading.overall_comment,
                rubric_scores=rubric_scores,
                revision_example=result.grading.revision_example,
            )
            logger.info(f"Updated Firestore: score={result.grading.total_score}/{result.grading.max_total_score}")

        # Send reply
        if result.counterpart_reply:

            # Build rubric breakdown for the reply email
            rubric_lines = []
            for s in result.grading.scores:
                line = f"  • {s.name}: {s.score}/{s.max_score}"
                if s.justification:
                    line += f" — {s.justification}"
                rubric_lines.append(line)
            rubric_section = "\n".join(rubric_lines)

            # Build a nice reply that includes the detailed feedback
            reply_body = (
                f"{result.counterpart_reply}\n\n"
                f"--- FEEDBACK ---\n"
                f"Score: {result.grading.total_score}/{result.grading.max_total_score}\n\n"
                f"Rubric Breakdown:\n{rubric_section}\n\n"
                f"{result.grading.overall_comment}"
            )

            # Add revision example if available
            if result.grading.revision_example:
                reply_body += (
                    f"\n\n--- EXAMPLE: How to get 100% ---\n"
                    f"{result.grading.revision_example}"
                )

            send_reply(service, msg, reply_body)
        else:
            logger.warning(f"Agent returned empty response for {sender}.")
            
    except Exception as e:
        logger.error(f"Error inside process_single_message: {e}", exc_info=True)

@log_function
def send_reply(service, original_msg, reply_text):
    """Sends a reply via Gmail API."""
    try:
        thread_id = original_msg['threadId']
        headers = original_msg['payload']['headers']
        subject = get_header(headers, 'Subject', 'No Subject')
        
        sender_email = get_header(headers, 'From', '')
        
        # Get the Message-ID from the original email for proper threading
        message_id = get_header(headers, 'Message-ID') or None
        
        logger.info(f"Constructing reply message for thread: {thread_id}")

        # Prepare Message with proper threading headers
        message_content = f"To: {sender_email}\r\n" \
                          f"Subject: Re: {subject}\r\n"
        
        # Add threading headers if we have the original Message-ID
        if message_id:
            message_content += f"In-Reply-To: {message_id}\r\n" \
                               f"References: {message_id}\r\n"
        
        message_content += f"\r\n{reply_text}"
        
        raw_message = base64.urlsafe_b64encode(message_content.encode("utf-8")).decode("utf-8")
        
        body = {'raw': raw_message, 'threadId': thread_id}
        
        sent_msg = service.users().messages().send(userId='me', body=body).execute()
        logger.info(f"Reply SENT successfully. ID: {sent_msg.get('id')}")
        
    except Exception as e:
        logger.error(f"Error sending reply: {e}", exc_info=True)

@log_function
def get_gmail_service():
    """Builds Gmail service using OAuth credentials fetched from Secret Manager via IAM."""
    try:
        # Get project ID from environment or metadata
        project_id = os.environ.get('GCP_PROJECT') or os.environ.get('GOOGLE_CLOUD_PROJECT')
        if not project_id:
            # Fallback: get from metadata service
            import requests
            metadata_server = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
            headers = {"Metadata-Flavor": "Google"}
            project_id = requests.get(metadata_server, headers=headers).text
        
        # Initialize Secret Manager client (uses service account IAM automatically)
        client = secretmanager.SecretManagerServiceClient()
        
        # Fetch OAuth credentials from Secret Manager
        def get_secret(secret_id):
            name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode('UTF-8').strip()
        
        client_id = get_secret('gmail-client-id')
        client_secret = get_secret('gmail-client-secret')
        
        # Refresh token secret is stored as JSON with metadata by get_token.py
        # Format: {"refresh_token": "...", "generated_at": "...", ...}
        refresh_token_raw = get_secret('gmail-refresh-token-bot')
        try:
            token_data = json.loads(refresh_token_raw)
            refresh_token = token_data['refresh_token']
        except (json.JSONDecodeError, KeyError):
            # Fallback: treat as plain string (backwards compat)
            refresh_token = refresh_token_raw
        

        
        # Build OAuth credentials
        creds = Credentials(
            None,  # No access token initially
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        logger.error(f"Auth error: {e}", exc_info=True)
        return None


# ============================================================================
# Gmail Watch Renewal (lazy, distributed-safe)
# ============================================================================

# Module-level cache: avoids Firestore reads within the same instance
_watch_expires_at: datetime | None = None

_WATCH_TOPIC = "projects/pathway-email-bot-6543/topics/email-notifications"
_WATCH_DOC_PATH = ("system", "watch_status")
_WATCH_RENEW_BUFFER = timedelta(hours=24)  # renew when <24h left
_WATCH_CLAIM_TIMEOUT = timedelta(seconds=60)  # stale claim threshold
_WATCH_DURATION = timedelta(days=7)  # Gmail watch expiry


def _ensure_watch(gmail_service):
    """
    Renew Gmail push-notification watch if nearing expiry.

    Uses a two-phase approach to prevent thundering herd:
      1. Firestore transaction claims renewal (only one instance wins)
      2. Winner calls Gmail watch() API
      3. Winner writes 'completed' status back to Firestore
    If the winner crashes, the claim expires after 60s so others can retry.
    """
    global _watch_expires_at
    now = datetime.now(timezone.utc)

    # Fast path: in-memory cache says watch is still fresh
    if _watch_expires_at and _watch_expires_at > now + _WATCH_RENEW_BUFFER:
        return

    from .firestore_client import get_firestore_client
    db = get_firestore_client()
    doc_ref = db.collection(*_WATCH_DOC_PATH[:1]).document(_WATCH_DOC_PATH[1])

    # Phase 1: Try to claim renewal via transaction
    transaction = db.transaction()
    if not _try_claim_watch_renewal(transaction, doc_ref, now):
        # Another instance is handling it, or watch is still fresh
        # Update local cache from the Firestore doc we just read
        snap = doc_ref.get()
        if snap.exists:
            data = snap.to_dict()
            exp = data.get('expires_at')
            if exp:
                _watch_expires_at = exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)
        return

    # Phase 2: We won the claim — call watch()
    try:
        gmail_service.users().watch(
            userId='me',
            body={'labelIds': ['INBOX'], 'topicName': _WATCH_TOPIC}
        ).execute()
    except Exception as e:
        logger.warning(f"Gmail watch renewal failed: {e}", exc_info=True)
        return  # claim will expire in 60s, another instance can retry

    # Phase 3: Confirm success
    new_expires = now + _WATCH_DURATION
    doc_ref.update({
        'status': 'completed',
        'expires_at': new_expires,
        'completed_at': now,
    })
    _watch_expires_at = new_expires
    logger.info(f"Gmail watch renewed — expires {new_expires.isoformat()}")


@firestore_lib.transactional
def _try_claim_watch_renewal(transaction, doc_ref, now: datetime) -> bool:
    """Transactional wrapper — reads doc in transaction, delegates to pure logic."""
    snapshot = doc_ref.get(transaction=transaction)
    data = snapshot.to_dict() if snapshot.exists else {}
    should_claim = _check_and_claim_watch(data, now)
    if should_claim:
        transaction.set(doc_ref, {
            'status': 'renewing',
            'claimed_at': now,
            'expires_at': data.get('expires_at'),  # preserve old value
        })
    return should_claim


def _check_and_claim_watch(data: dict, now: datetime) -> bool:
    """
    Pure decision logic: should this instance claim watch renewal?

    Returns True if renewal is needed, False to skip.
    Testable without Firestore mocks.
    """
    expires_at = data.get('expires_at')
    status = data.get('status')
    claimed_at = data.get('claimed_at')

    # Normalise timestamps to UTC-aware
    if expires_at and not getattr(expires_at, 'tzinfo', None):
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if claimed_at and not getattr(claimed_at, 'tzinfo', None):
        claimed_at = claimed_at.replace(tzinfo=timezone.utc)

    # Case 1: Watch is fresh and confirmed — skip
    if (status == 'completed'
            and expires_at
            and expires_at > now + _WATCH_RENEW_BUFFER):
        return False

    # Case 2: Another instance is currently renewing (< 60s ago) — skip
    if (status == 'renewing'
            and claimed_at
            and (now - claimed_at) < _WATCH_CLAIM_TIMEOUT):
        return False

    # Case 3: Needs renewal (expired, never set, or claimer timed out)
    return True


# ============================================================================
# Name personalisation helpers
# ============================================================================

_STUDENT_NAME_PLACEHOLDER = "{student_name}"


def _personalize_body(body: str, first_name: str | None) -> str:
    """Replace {student_name} placeholder with the student's first name.

    Names are validated at write time by Firestore security rules, so
    any value that made it into Firestore is trusted here.

    If no name is set, the placeholder is removed so
    "Hi {student_name}," gracefully becomes "Hi ,".
    """
    if _STUDENT_NAME_PLACEHOLDER not in body:
        return body

    if first_name:
        return body.replace(_STUDENT_NAME_PLACEHOLDER, first_name)

    # No name — remove placeholder
    return body.replace(_STUDENT_NAME_PLACEHOLDER, "")


# ============================================================================
# HTTP Cloud Function: start_scenario
# ============================================================================

@log_function
def _verify_token(request: Request) -> str | None:
    """
    Verify Firebase ID token from Authorization header.
    Returns email if valid, None otherwise.
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    
    try:
        id_token = auth_header[7:]  # Remove 'Bearer ' prefix
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded.get('email')
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None


@log_function
def _build_mime_message(from_addr: str, from_name: str, to_addr: str, subject: str, body: str) -> str:
    """
    Build a MIME message and return as base64-encoded string for Gmail API.
    """
    message = MIMEText(body, 'plain')
    message['To'] = to_addr
    message['From'] = f'{from_name} <{from_addr}>'
    message['Subject'] = subject
    
    # Encode for Gmail API
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return raw_message


@functions_framework.http
@log_function
def start_scenario(request: Request):
    """
    HTTP Cloud Function to start a scenario for a student.

    Handles both INITIATE and REPLY scenarios:
      - Creates Firestore attempt (server-side, single source of truth)
      - Ensures Gmail watch is active
      - For REPLY scenarios: also sends the starter email from the bot

    Request body:
    {
        "email": "student@example.com",
        "scenarioId": "missed_remote_standup"
    }

    Response:
    {
        "success": true,
        "attemptId": "uuid-here",
        "message": "Scenario started"
    }
    """
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': 'https://pathway-email-bot.github.io',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)
    
    # CORS headers for response
    cors_headers = {
        'Access-Control-Allow-Origin': 'https://pathway-email-bot.github.io',
        'Content-Type': 'application/json',
    }
    
    try:
        # Verify Firebase ID token
        token_email = _verify_token(request)
        if not token_email:
            return {'error': 'Unauthorized: Invalid or missing token'}, 401, cors_headers
        
        # Parse request JSON
        request_json = request.get_json() or {}
        student_email = request_json.get('email')
        scenario_id = request_json.get('scenarioId')
        
        # Validate request
        if not student_email:
            return {'error': 'Missing email in request'}, 400, cors_headers
        if not scenario_id:
            return {'error': 'Missing scenarioId in request'}, 400, cors_headers
        
        # Verify user is requesting for their own email
        if student_email != token_email:
            logger.warning(f"Email mismatch: token={token_email}, request={student_email}")
            return {'error': 'Cannot start scenario for another user'}, 403, cors_headers
        
        # Load scenario
        scenario_path = BASE_DIR / 'email_agent' / 'scenarios' / f'{scenario_id}.json'
        if not scenario_path.exists():
            logger.warning(f"Scenario not found: {scenario_id}")
            return {'error': f'Scenario not found: {scenario_id}'}, 404, cors_headers
        
        scenario = load_scenario(scenario_path)
        logger.info(f"Loaded scenario: {scenario_id} (type={scenario.interaction_type})")
        
        # Ensure Gmail watch is active
        gmail_service = get_gmail_service()
        if not gmail_service:
            logger.error("Failed to initialize Gmail service")
            return {'error': 'Gmail service initialization failed'}, 500, cors_headers
        
        _ensure_watch(gmail_service)
        
        # For REPLY scenarios, send the starter email BEFORE creating the attempt.
        # This way a failed email send won't leave a stale "pending" attempt.
        if scenario.interaction_type == 'reply':
            # Read student's first name for email personalisation (single read)
            from .firestore_client import get_firestore_client
            user_doc = get_firestore_client().collection('users').document(student_email).get()
            first_name = user_doc.to_dict().get('firstName') if user_doc.exists else None

            from_name = scenario.starter_sender_name
            subject = f"[PEB:{scenario_id}] {scenario.starter_subject}"
            body = _personalize_body(scenario.starter_email_body, first_name)
            
            raw_message = _build_mime_message(
                from_addr=BOT_EMAIL,
                from_name=from_name,
                to_addr=student_email,
                subject=subject,
                body=body
            )
            
            gmail_service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
            logger.info(f"Starter email sent to {student_email} for scenario {scenario_id}")
        
        # Create Firestore attempt only after all fallible work succeeds
        from .firestore_client import create_attempt
        attempt_id = create_attempt(student_email, scenario_id)
        logger.info(f"Created attempt {attempt_id} for {student_email}")
        
        return {
            'success': True,
            'attemptId': attempt_id,
            'message': f'Scenario started: {scenario_id}',
        }, 200, cors_headers
        
    except Exception as e:
        logger.error(f"Error in start_scenario: {e}", exc_info=True)
        return {'error': str(e)}, 500, cors_headers

