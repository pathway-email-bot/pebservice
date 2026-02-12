"""
Pathway Email Bot (PEB) - Cloud Functions Main Entry Point

This file contains TWO separate Google Cloud Functions that share the same codebase:

1. process_email (Cloud Event / Pub/Sub trigger)
   - Triggered by Gmail push notifications when student sends email
   - Fetches email, grades it using EmailAgent + rubric, saves to Firestore, sends reply
   - Deployed as: gcloud functions deploy process_email --trigger-topic=gmail-notifications

2. send_scenario_email (HTTP trigger)
   - Called by portal frontend to send scenario starter email (REPLY scenarios only)
   - Validates Firebase auth token, loads scenario, sends email via Gmail API
   - Deployed as: gcloud functions deploy send_scenario_email --trigger-http

Both functions deploy from this same source directory (./service) and share:
  - email_agent/ (scenario loading, grading logic, email agent)
  - auth_utils.py, firestore_client.py (shared utilities)
  - Scenario and rubric JSON files

This architecture is required by Cloud Functions deployment model, which needs a main.py
file at the root of the source directory.
"""

import base64
import json
import os
import logging
from pathlib import Path
from email.mime.text import MIMEText

import functions_framework
from flask import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.cloud import secretmanager
import firebase_admin
from firebase_admin import auth as firebase_auth

from .email_agent.scenario_loader import load_scenario
from .email_agent.rubric_loader import load_rubric
from .email_agent.email_agent import EmailAgent, EmailMessage
from .logging_utils import log_function

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin (only once, shared by both functions)
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

# Constants - Path resolution
# Note: email_agent/ directory structure is preserved in Cloud Functions deployment
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SCENARIO_PATH = BASE_DIR / "email_agent/scenarios/missed_remote_standup.json"
DEFAULT_RUBRIC_PATH = BASE_DIR / "email_agent/rubrics/default.json"

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
            update_attempt_graded(
                email=sender_email,
                attempt_id=attempt_id,
                score=result.grading.total_score,
                max_score=result.grading.max_total_score,
                feedback=result.grading.overall_comment
            )
            logger.info(f"Updated Firestore: score={result.grading.total_score}/{result.grading.max_total_score}")

        # Send reply
        if result.counterpart_reply:

            # Build a nice reply that includes the feedback
            reply_body = (
                f"{result.counterpart_reply}\n\n"
                f"--- FEEDBACK ---\n"
                f"{result.grading.overall_comment}\n\n"
                f"Score: {result.grading.total_score}/{result.grading.max_total_score}"
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
# HTTP Cloud Function: send_scenario_email
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
def send_scenario_email(request: Request):
    """
    HTTP Cloud Function to send scenario email (REPLY scenarios only).
    Portal creates Firestore attempt BEFORE calling this function.
    This function is ONLY for sending email.
    
    Request body:
    {
        "email": "student@example.com",
        "scenarioId": "missed_remote_standup",
        "attemptId": "abc123"
    }
    
    Response:
    {
        "success": true,
        "message": "Scenario email sent"
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
        attempt_id = request_json.get('attemptId')
        
        # Validate request
        if not student_email:
            return {'error': 'Missing email in request'}, 400, cors_headers
        if not scenario_id:
            return {'error': 'Missing scenarioId in request'}, 400, cors_headers
        if not attempt_id:
            return {'error': 'Missing attemptId in request'}, 400, cors_headers
        
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
        logger.info(f"Loaded scenario: {scenario_id}")
        
        # Verify this is a REPLY scenario (bot sends first)
        if scenario.interaction_type != 'reply':
            logger.warning(f"Attempt to send email for INITIATE scenario: {scenario_id}")
            return {'error': 'This endpoint is only for REPLY scenarios. INITIATE scenarios do not send emails.'}, 400, cors_headers
        
        # Generate starter email using EmailAgent
        email_agent = EmailAgent()
        starter_thread = email_agent.build_starter_thread(scenario)
        starter_message = starter_thread.messages[0]  # The bot's starter email
        
        logger.info(f"Generated starter email for {scenario_id}")
        
        # Send email via Gmail API (authenticated as bot account)
        gmail_service = get_gmail_service()
        if not gmail_service:
            logger.error("Failed to initialize Gmail service")
            return {'error': 'Gmail service initialization failed'}, 500, cors_headers
        
        from_name = scenario.starter_sender_name
        subject = f"[PEB:{scenario_id}] {scenario.starter_subject}"
        body = starter_message.content
        
        raw_message = _build_mime_message(
            from_addr='pathwayemailbot@gmail.com',
            from_name=from_name,
            to_addr=student_email,
            subject=subject,
            body=body
        )
        
        gmail_service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        logger.info(f"Email sent to {student_email} for scenario {scenario_id} (attempt {attempt_id})")
        
        return {
            'success': True,
            'message': f'Scenario email sent to {student_email}',
        }, 200, cors_headers
        
    except Exception as e:
        logger.error(f"Error in send_scenario_email: {e}", exc_info=True)
        return {'error': str(e)}, 500, cors_headers

