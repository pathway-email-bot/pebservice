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
from datetime import datetime, timezone
from pathlib import Path

import functions_framework
from flask import Request

import firebase_admin

from .email_agent.scenario_loader import load_scenario
from .email_agent.rubric_loader import load_rubric
from .email_agent.scenario_models import InteractionType
from .email_agent.email_agent import EmailAgent, EmailMessage
from .logging_utils import log_function, setup_cloud_logging
from .gmail_client import (
    get_gmail_service,
    send_reply,
    build_mime_message,
    ensure_watch,
    extract_email_body,
)
from .secrets import get_openai_api_key
from .auth import verify_token

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

# Constants
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RUBRIC_PATH = BASE_DIR / "email_agent/rubrics/peb_rubric_v1.json"
BOT_EMAIL = "pathwayemailbot@gmail.com"
CORS_ORIGIN = "https://pathway-email-bot.github.io"

# Canary log to verify logging is working in Cloud Functions
logger.info("PEB Service module loaded. Logging is operational.")


def get_header(headers, name, default=""):
    """Case-insensitive header lookup."""
    name_lower = name.lower()
    return next((h['value'] for h in headers if h['name'].lower() == name_lower), default)


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
# Cloud Event Function: process_email
# ============================================================================

@functions_framework.cloud_event
@log_function
def process_email(cloud_event):
    """Triggered from a message on a Cloud Pub/Sub topic.

    The message usually comes from Gmail push notifications.
    """
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

            service = get_gmail_service()
            if not service:
                logger.error("Failed to initialize Gmail service")
                return "OK"

            try:
                logger.debug(f"Fetching history starting from historyId={history_id}")
                history = service.users().history().list(userId='me', startHistoryId=history_id).execute()
                changes = history.get('history', [])

                if not changes:
                    logger.debug("No history changes found. Attempting fallback to latest message.")
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


@log_function
def process_single_message(service, msg):
    """Parse email content and grade it."""
    try:
        from .firestore_client import get_active_scenario, update_attempt_graded, get_firestore_client

        headers = msg.get('payload', {}).get('headers', [])
        subject = get_header(headers, 'Subject', 'No Subject')
        sender = get_header(headers, 'From', 'Unknown')

        # Extract sender email from "Name <email@example.com>" format
        sender_email = sender
        if '<' in sender and '>' in sender:
            sender_email = sender.split('<')[1].split('>')[0].strip()

        # Extract body using robust MIME parsing
        body = extract_email_body(msg) or "No Body"

        logger.info(f"Email from: {sender_email} | Subject: {subject}")

        # Guard: Don't reply to self or bots to avoid loops
        if "google" in sender.lower() or "bot" in sender.lower() or "noreply" in sender.lower():
             logger.info(f"Skipping auto-reply for likely bot/self: {sender}")
             return

        # Get active scenario from Firestore
        active_scenario = get_active_scenario(sender_email)

        if not active_scenario:
            logger.warning(f"No active scenario found for {sender_email}")

            redirect_message = (
                "Thanks for your email! To practice email scenarios, please visit the student portal "
                "and click 'Start' on a scenario first. Then reply to the scenario email you receive.\n\n"
                "Portal: https://pathway-email-bot.github.io/pebservice/"
            )
            send_reply(service, msg, redirect_message)
            return

        scenario_id, attempt_id = active_scenario
        logger.info(f"Found active scenario: {scenario_id} (attempt: {attempt_id})")

        # --- Idempotency guard: skip if already graded ---
        db = get_firestore_client()
        attempt_ref = db.collection('users').document(sender_email).collection('attempts').document(attempt_id)
        attempt_doc = attempt_ref.get()
        if attempt_doc.exists and attempt_doc.to_dict().get('status') == 'graded':
            logger.info(f"Attempt {attempt_id} already graded — skipping duplicate")
            return

        # Load scenario and rubric
        scenario = load_scenario(scenario_id)
        rubric = load_rubric(DEFAULT_RUBRIC_PATH)

        # Get OpenAI API key
        api_key = get_openai_api_key()
        if not api_key:
            logger.error("Missing OPENAI_API_KEY")
            return

        agent = EmailAgent(
            model="gpt-4o",
            temperature=0.2,
            scenario=scenario,
            api_key=api_key
        )

        student_email = EmailMessage(
            sender=sender,
            subject=subject,
            body=body
        )

        prior_thread = agent.build_starter_thread()

        result = agent.evaluate_and_respond(
            prior_thread=prior_thread,
            student_email=student_email,
            rubric=rubric.items
        )

        # Update Firestore with grading results
        if result.grading:
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
            rubric_lines = []
            for s in result.grading.scores:
                line = f"  • {s.name}: {s.score}/{s.max_score}"
                if s.justification:
                    line += f" — {s.justification}"
                rubric_lines.append(line)
            rubric_section = "\n".join(rubric_lines)

            reply_body = (
                f"{result.counterpart_reply}\n\n"
                f"--- FEEDBACK ---\n"
                f"Score: {result.grading.total_score}/{result.grading.max_total_score}\n\n"
                f"Rubric Breakdown:\n{rubric_section}\n\n"
                f"{result.grading.overall_comment}"
            )

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


# ============================================================================
# HTTP Cloud Function: start_scenario
# ============================================================================

@functions_framework.http
@log_function
def start_scenario(request: Request):
    """HTTP Cloud Function to start a scenario for a student.

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
            'Access-Control-Allow-Origin': CORS_ORIGIN,
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    cors_headers = {
        'Access-Control-Allow-Origin': CORS_ORIGIN,
        'Content-Type': 'application/json',
    }

    try:
        # Verify Firebase ID token
        token_email = verify_token(request)
        if not token_email:
            return {'error': 'Unauthorized: Invalid or missing token'}, 401, cors_headers

        # Parse request JSON
        request_json = request.get_json() or {}
        student_email = request_json.get('email')
        scenario_id = request_json.get('scenarioId')

        if not student_email:
            return {'error': 'Missing email in request'}, 400, cors_headers
        if not scenario_id:
            return {'error': 'Missing scenarioId in request'}, 400, cors_headers

        # Verify user is requesting for their own email
        if student_email != token_email:
            logger.warning(f"Email mismatch: token={token_email}, request={student_email}")
            return {'error': 'Cannot start scenario for another user'}, 403, cors_headers

        # Load scenario
        from .firestore_client import get_firestore_client, create_attempt
        db = get_firestore_client()
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

        ensure_watch(gmail_service)

        # For REPLY scenarios, send the starter email BEFORE creating the attempt.
        if scenario.interaction_type == InteractionType.REPLY:
            user_doc = db.collection('users').document(student_email).get()
            first_name = user_doc.to_dict().get('firstName') if user_doc.exists else None

            from_name = scenario.starter_sender_name
            subject = f"[PEB:{scenario_id}] {scenario.starter_subject}"
            body = _personalize_body(scenario.starter_email_body, first_name)

            raw_message = build_mime_message(
                from_addr=BOT_EMAIL,
                from_name=from_name,
                to_addr=student_email,
                subject=subject,
                body=body
            )

            gmail_service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
            logger.info(f"Starter email sent to {student_email} for scenario {scenario_id}")

        # Create Firestore attempt only after all fallible work succeeds
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
