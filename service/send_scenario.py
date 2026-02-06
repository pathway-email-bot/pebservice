"""
HTTP Cloud Function to send scenario emails to students.
Endpoint: POST /sendScenarioEmail

Authenticated via: Firebase ID token
"""
import functions_framework
from flask import Request
import firebase_admin
from firebase_admin import auth as firebase_auth
import logging
from pathlib import Path
import base64
from email.mime.text import MIMEText

from email_agent.scenario_loader import load_scenario
from email_agent.email_agent import EmailAgent
from auth_utils import get_gmail_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin (only once)
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

BASE_DIR = Path(__file__).resolve().parent


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
    logger.info(f"send_scenario_email called: method={request.method}")
    
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
        
        # Send email via Gmail API
        gmail_service = get_gmail_service(student_email)
        
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
