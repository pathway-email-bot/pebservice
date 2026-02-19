"""
Pathway Email Bot (PEB) - Cloud Functions Main Entry Point

This file contains THREE separate Google Cloud Functions that share the same codebase:

1. process_email (Cloud Event / Pub/Sub trigger)
   - Triggered by Gmail push notifications when student sends email
   - Fetches email, grades it using EmailAgent + rubric, saves to Firestore, sends reply
   - Deployed as: gcloud functions deploy process_email --trigger-topic=gmail-notifications

2. start_scenario (HTTP trigger)
   - Called by portal frontend to start a scenario (INITIATE or REPLY)
   - Validates Firebase auth, creates Firestore attempt, ensures Gmail watch
   - For REPLY scenarios: also sends starter email via Gmail API
   - Deployed as: gcloud functions deploy start_scenario --trigger-http

3. send_magic_link (HTTP trigger, unauthenticated)
   - Called by portal to send a sign-in magic link via bot's Gmail
   - Generates link via Admin SDK, sends via Gmail API (avoids Firebase's shared domain)
   - Deployed as: gcloud functions deploy send_magic_link --trigger-http --allow-unauthenticated

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
        if sender_email == BOT_EMAIL or "noreply" in sender_email.lower():
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


# ============================================================================
# HTTP Cloud Function: send_magic_link (unauthenticated)
# ============================================================================

# Continue URL for magic link — where users land after clicking the link
MAGIC_LINK_CONTINUE_URL = CORS_ORIGIN + "/pebservice/"

# ---------- In-memory rate limiting ----------
# Cloud Functions instances persist between requests, so module-level state
# acts as a per-instance cache. In a scale-out event each instance gets its
# own cache, which means rate limits are "best-effort" — but sufficient to
# stop simple abuse scripts (a determined attacker hitting multiple instances
# isn't stopped, but Gmail's 500/day cap is the hard backstop).
import threading
from collections import deque

_rate_lock = threading.Lock()
_email_last_sent: dict[str, float] = {}              # email → last send timestamp
_ip_request_log: dict[str, deque[float]] = {}        # ip → deque(maxlen=5) of timestamps

# Rate limit constants
_EMAIL_COOLDOWN_SECS = 60   # 1 magic link per email per 60 seconds
_IP_MAX_RPS = 5             # max 5 requests/second per IP
_IP_WINDOW_SECS = 1.0       # sliding window for IP rate limiting


def _get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For (set by Cloud Run/Functions)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        # First IP in comma-separated list is the original client
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _check_rate_limit(email: str, client_ip: str) -> str | None:
    """Return an error message if rate-limited, None if OK."""
    import time
    now = time.monotonic()

    with _rate_lock:
        # --- Per-IP: ring buffer of last 5 request timestamps (O(1)) ---
        if client_ip not in _ip_request_log:
            _ip_request_log[client_ip] = deque(maxlen=_IP_MAX_RPS)

        ring = _ip_request_log[client_ip]
        ring.append(now)  # auto-evicts oldest if full; always counted

        if len(ring) >= _IP_MAX_RPS and (now - ring[0]) < _IP_WINDOW_SECS:
            return "Too many requests. Please wait a moment and try again."

        # --- Per-email cooldown ---
        last = _email_last_sent.get(email)
        if last and (now - last) < _EMAIL_COOLDOWN_SECS:
            remaining = int(_EMAIL_COOLDOWN_SECS - (now - last))
            return f"Please wait {remaining}s before requesting another link for this email."

        # Both checks passed — record email send time
        _email_last_sent[email] = now

    return None  # OK


@functions_framework.http
@log_function
def send_magic_link(request: Request):
    """HTTP Cloud Function to send a sign-in magic link via Gmail API.

    Replaces Firebase's default magic link email (sent from the shared
    noreply@...firebaseapp.com domain) with one sent from the bot's own
    Gmail account, which has proper DKIM signing and better deliverability.

    This endpoint is UNAUTHENTICATED because it serves the login flow
    (the user isn't signed in yet). Protections:
      - CORS restricted to CORS_ORIGIN
      - Email format validation
      - Per-email rate limit (1 per 60s)
      - Per-IP rate limit (5 RPS)
      - Firebase magic links are one-time-use tokens
      - Gmail API has built-in daily sending limits

    Request body:
    {
        "email": "student@example.com"
    }

    Response:
    {
        "success": true
    }
    """
    import re
    from firebase_admin import auth as firebase_auth

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': CORS_ORIGIN,
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    cors_headers = {
        'Access-Control-Allow-Origin': CORS_ORIGIN,
        'Content-Type': 'application/json',
    }

    try:
        # Parse and validate email
        request_json = request.get_json() or {}
        email = request_json.get('email', '').strip().lower()

        if not email:
            return {'error': 'Missing email in request'}, 400, cors_headers

        # Basic email format validation
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return {'error': 'Invalid email format'}, 400, cors_headers

        # Extract IP and log for abuse debugging
        # (GCP _Default log bucket auto-deletes after 30 days)
        client_ip = _get_client_ip(request)
        logger.info(f"Magic link request: email={email} ip={client_ip}")

        # Rate limiting
        rate_error = _check_rate_limit(email, client_ip)
        if rate_error:
            logger.warning(f"Rate limited: email={email} ip={client_ip} reason={rate_error}")
            return {'error': rate_error}, 429, cors_headers

        # Generate the magic link server-side (does NOT send an email)
        action_code_settings = firebase_auth.ActionCodeSettings(
            url=MAGIC_LINK_CONTINUE_URL,
            handle_code_in_app=True,
        )

        link = firebase_auth.generate_sign_in_with_email_link(
            email, action_code_settings
        )

        logger.info(f"Magic link generated for {email}")

        # Send via Gmail API
        gmail_service = get_gmail_service()
        if not gmail_service:
            logger.error("Failed to initialize Gmail service for magic link")
            return {'error': 'Email service unavailable'}, 500, cors_headers

        email_body = (
            f"Hello,\n\n"
            f"Click the link below to sign in to Pathway Email Bot:\n\n"
            f"{link}\n\n"
            f"This link expires in 1 hour and can only be used once.\n\n"
            f"If you did not request this, you can safely ignore this email.\n\n"
            f"— Pathway Email Bot"
        )

        email_html = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5; padding:40px 20px;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#E87722,#C45A00); padding:32px 40px; text-align:center;">
          <h1 style="margin:0; color:#ffffff; font-size:22px; font-weight:600; letter-spacing:-0.3px;">
            &#x1F4E7; Pathway Email Bot
          </h1>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:36px 40px;">
          <p style="margin:0 0 20px; color:#374151; font-size:16px; line-height:1.6;">
            Hello! Click the button below to sign in:
          </p>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td align="center" style="padding:8px 0 28px;">
              <a href="{link}" target="_blank"
                 style="display:inline-block; background:#E87722; color:#ffffff; padding:14px 40px;
                        border-radius:8px; font-size:16px; font-weight:600; text-decoration:none;
                        letter-spacing:0.2px; box-shadow:0 2px 4px rgba(232,119,34,0.3);">
                Sign in to Pathway Email Bot
              </a>
            </td></tr>
          </table>
          <p style="margin:0 0 6px; color:#6b7280; font-size:13px; line-height:1.5;">
            Or copy and paste this link into your browser:
          </p>
          <p style="margin:0 0 24px; word-break:break-all; color:#E87722; font-size:13px; line-height:1.5;">
            {link}
          </p>
          <hr style="border:none; border-top:1px solid #e5e7eb; margin:0 0 20px;">
          <p style="margin:0; color:#9ca3af; font-size:12px; line-height:1.5;">
            This link expires in 1 hour and can only be used once.<br>
            If you didn&rsquo;t request this email, you can safely ignore it.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

        raw_message = build_mime_message(
            from_addr=BOT_EMAIL,
            from_name="Pathway Email Bot",
            to_addr=email,
            subject="Sign in to Pathway Email Bot",
            body=email_body,
            html=email_html,
        )

        gmail_service.users().messages().send(
            userId='me', body={'raw': raw_message}
        ).execute()

        logger.info(f"Magic link email sent to {email} via Gmail API")

        return {'success': True}, 200, cors_headers

    except Exception as e:
        logger.error(f"Error in send_magic_link: {e}", exc_info=True)
        return {'error': 'Failed to send sign-in link. Please try again.'}, 500, cors_headers


# ============================================================================
# HTTP Cloud Function: submit_feedback (unauthenticated)
# ============================================================================

# Feedback rate limiting — separate from magic link rate limits
_FEEDBACK_COOLDOWN_SECS = 5   # 1 feedback per 5 seconds per email or IP
_feedback_last_sent: dict[str, float] = {}   # key (email or IP) → timestamp


def _check_feedback_rate_limit(key: str) -> str | None:
    """Return an error message if feedback rate-limited, None if OK."""
    import time
    now = time.monotonic()

    with _rate_lock:
        last = _feedback_last_sent.get(key)
        if last and (now - last) < _FEEDBACK_COOLDOWN_SECS:
            return "Please wait a few seconds before sending more feedback."

        _feedback_last_sent[key] = now

    return None  # OK


@functions_framework.http
@log_function
def submit_feedback(request: Request):
    """HTTP Cloud Function to receive user feedback and email it to the bot inbox.

    Unauthenticated — anyone can submit feedback (login page users too).
    Rate-limited to 1 submit per 5 seconds per email or IP.

    Request body:
    {
        "message": "Great tool!",
        "stars": 4,
        "page": "scenarios",
        "email": "student@example.com",   // optional, auto-filled if logged in
        "consoleErrors": ["error1", ...]   // optional
    }

    Response:
    {
        "success": true
    }
    """

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': CORS_ORIGIN,
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    cors_headers = {
        'Access-Control-Allow-Origin': CORS_ORIGIN,
        'Content-Type': 'application/json',
    }

    try:
        request_json = request.get_json() or {}

        message = (request_json.get('message') or '').strip()
        stars = request_json.get('stars')
        page = (request_json.get('page') or 'unknown').strip()
        email = (request_json.get('email') or '').strip().lower()
        console_errors = request_json.get('consoleErrors') or []

        # Validate required fields
        if not message:
            return {'error': 'Message is required'}, 400, cors_headers
        if not isinstance(stars, int) or not (1 <= stars <= 5):
            return {'error': 'Stars must be an integer from 1 to 5'}, 400, cors_headers

        # Rate limit — key on email if provided, otherwise on IP
        client_ip = _get_client_ip(request)
        rate_key = email if email else client_ip
        rate_error = _check_feedback_rate_limit(rate_key)
        if rate_error:
            logger.warning(f"Feedback rate limited: key={rate_key} ip={client_ip}")
            return {'error': rate_error}, 429, cors_headers

        logger.info(f"Feedback received: stars={stars} page={page} email={email or 'anonymous'} ip={client_ip}")

        # Build the feedback email
        star_display = '★' * stars + '☆' * (5 - stars)
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        # Plain text version
        plain_lines = [
            f"New feedback from Pathway Email Bot",
            f"",
            f"Stars: {star_display} ({stars}/5)",
            f"Page:  {page}",
            f"From:  {email or 'anonymous'}",
            f"IP:    {client_ip}",
            f"Time:  {timestamp}",
            f"",
            f"Message:",
            f"{message}",
        ]
        if console_errors:
            plain_lines.append("")
            plain_lines.append("Console Errors:")
            for err in console_errors[:10]:
                plain_lines.append(f"  • {err}")

        email_body = "\n".join(plain_lines)

        # HTML version
        star_html = ''.join(
            f'<span style="color:#F59E0B;font-size:24px;">★</span>' if i < stars
            else f'<span style="color:#D1D5DB;font-size:24px;">☆</span>'
            for i in range(5)
        )

        error_section = ""
        if console_errors:
            error_items = "".join(
                f'<li style="margin-bottom:4px;font-family:monospace;font-size:12px;color:#991B1B;">{err}</li>'
                for err in console_errors[:10]
            )
            error_section = f"""
            <tr><td style="padding:16px 32px 24px;">
              <h3 style="margin:0 0 8px;color:#991B1B;font-size:14px;">🐛 Console Errors</h3>
              <ul style="margin:0;padding-left:20px;">{error_items}</ul>
            </td></tr>"""

        email_html = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background:#f4f4f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5; padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#E87722,#C45A00); padding:24px 32px; text-align:center;">
          <h1 style="margin:0; color:#ffffff; font-size:20px; font-weight:600;">
            💬 New Feedback
          </h1>
        </td></tr>
        <!-- Stars -->
        <tr><td style="padding:24px 32px 8px; text-align:center;">
          {star_html}
          <p style="margin:4px 0 0; color:#6B7280; font-size:14px;">{stars} out of 5 stars</p>
        </td></tr>
        <!-- Message -->
        <tr><td style="padding:16px 32px;">
          <h3 style="margin:0 0 8px; color:#374151; font-size:14px;">Message</h3>
          <div style="background:#F9FAFB; border:1px solid #E5E7EB; border-radius:8px; padding:16px; color:#374151; font-size:14px; line-height:1.6; white-space:pre-wrap;">{message}</div>
        </td></tr>
        <!-- Metadata -->
        <tr><td style="padding:8px 32px 24px;">
          <table width="100%" cellpadding="4" cellspacing="0" style="font-size:13px; color:#6B7280;">
            <tr><td style="font-weight:600;width:60px;">From</td><td>{email or 'anonymous'}</td></tr>
            <tr><td style="font-weight:600;">Page</td><td>{page}</td></tr>
            <tr><td style="font-weight:600;">IP</td><td>{client_ip}</td></tr>
            <tr><td style="font-weight:600;">Time</td><td>{timestamp}</td></tr>
          </table>
        </td></tr>{error_section}
      </table>
    </td></tr>
  </table>
</body>
</html>"""

        # Send via Gmail API to the bot's own inbox
        gmail_service = get_gmail_service()
        if not gmail_service:
            logger.error("Failed to initialize Gmail service for feedback")
            return {'error': 'Email service unavailable'}, 500, cors_headers

        raw_message = build_mime_message(
            from_addr=BOT_EMAIL,
            from_name="PEB Feedback",
            to_addr=BOT_EMAIL,
            subject=f"[Feedback] {star_display} — {page} page",
            body=email_body,
            html=email_html,
        )

        gmail_service.users().messages().send(
            userId='me', body={'raw': raw_message}
        ).execute()

        logger.info(f"Feedback email sent: stars={stars} from={email or 'anonymous'}")

        return {'success': True}, 200, cors_headers

    except Exception as e:
        logger.error(f"Error in submit_feedback: {e}", exc_info=True)
        return {'error': 'Failed to send feedback. Please try again.'}, 500, cors_headers

