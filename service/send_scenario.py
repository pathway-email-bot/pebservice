"""
HTTP Cloud Function to send scenario emails to students.
Endpoint: POST /sendScenarioEmail
"""
import functions_framework
from flask import jsonify, Request
import firebase_admin
from firebase_admin import auth as firebase_auth
import json
import os
from pathlib import Path
from email_agent.scenario_loader import load_scenario
from email_agent.email_agent import EmailAgent
from firestore_client import create_attempt
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import base64
from email.mime.text import MIMEText

# Initialize Firebase Admin (only once)
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

def get_gmail_service():
    """Get Gmail API service using stored credentials"""
    # Use the same credential logic as main.py
    from auth_utils import get_gmail_credentials
    creds = get_gmail_credentials()
    return build('gmail', 'v1', credentials=creds)

def send_email(service, to: str, subject: str, body: str, from_name: str = None):
    """Send an email via Gmail API"""
    from_email = "pathwayemailbot@gmail.com"
    if from_name:
        from_header = f'"{from_name}" <{from_email}>'
    else:
        from_header = from_email
    
    message = MIMEText(body)
    message['to'] = to
    message['from'] = from_header
    message['subject'] = subject
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()

@functions_framework.http
def send_scenario_email(request: Request):
    """
    HTTP Cloud Function to send scenario email.
    
    Request body:
    {
        "email": "student@example.com",
        "scenarioId": "missed_remote_standup"
    }
    
    Response:
    {
        "success": true,
        "attemptId": "abc123",
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
    
    # Set CORS headers for actual request
    headers = {
        'Access-Control-Allow-Origin': 'https://pathway-email-bot.github.io',
    }
    
    try:
        # Verify Firebase ID token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401, headers
        
        id_token = auth_header.split('Bearer ')[1]
        decoded_token = firebase_auth.verify_id_token(id_token)
        authenticated_email = decoded_token['email']
        
        # Parse request
        request_json = request.get_json()
        student_email = request_json.get('email')
        scenario_id = request_json.get('scenarioId')
        
        if not student_email or not scenario_id:
            return jsonify({'error': 'Missing email or scenarioId'}), 400, headers
        
        # Verify user is requesting for their own email
        if student_email != authenticated_email:
            return jsonify({'error': 'Cannot start scenario for another user'}), 403, headers
        
        # Load scenario
        scenario_path = Path(__file__).parent / 'email_agent' / 'scenarios' / f'{scenario_id}.json'
        if not scenario_path.exists():
            return jsonify({'error': f'Scenario {scenario_id} not found'}), 404, headers
        
        scenario = load_scenario(scenario_id)
        
        # Create Firestore attempt
        attempt_id = create_attempt(student_email, scenario_id)
        
        # Build starter email
        agent = EmailAgent(scenario=scenario, rubric=None)  # Rubric loaded internally
        starter_thread = agent.build_starter_thread()
        
        # Send email
        gmail_service = get_gmail_service()
        from_name = scenario.starter_sender_name if hasattr(scenario, 'starter_sender_name') else "Email Bot"
        subject = f"[PEB:{scenario_id}] {scenario.name}"
        
        send_email(
            gmail_service,
            to=student_email,
            subject=subject,
            body=starter_thread,
            from_name=from_name
        )
        
        return jsonify({
            'success': True,
            'attemptId': attempt_id,
            'message': 'Scenario email sent'
        }), 200, headers
        
    except Exception as e:
        import logging
        logging.error(f"Error sending scenario email: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500, headers
