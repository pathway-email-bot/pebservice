import base64
import json
import os
import logging
from pathlib import Path

import functions_framework
from google.cloud import pubsub_v1
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from email_agent.scenario_loader import load_scenario
from email_agent.rubric_loader import load_rubric
from email_agent.email_agent import EmailAgent, EmailMessage

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_DIR = Path(__file__).resolve().parent / "email_agent"
DEFAULT_SCENARIO_PATH = BASE_DIR / "scenarios/missed_remote_standup.json"
DEFAULT_RUBRIC_PATH = BASE_DIR / "rubrics/default.json"

@functions_framework.cloud_event
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
        logger.info(f"Received message: {message_data}")
        
        try:
            notification = json.loads(message_data)
            email_address = notification.get("emailAddress")
            history_id = notification.get("historyId")
            
            if not history_id:
                logger.warning("No historyId found in notification.")
                return "OK"
                
            logger.info(f"Notification for {email_address}, historyId: {history_id}")
            
            # 2. Initialize Gmail Service
            service = get_gmail_service()
            if not service:
                logger.error("Failed to initialize Gmail service.")
                return "OK"

            # 3. List history to find the message ID
            try:
                history = service.users().history().list(userId='me', startHistoryId=history_id).execute()
                changes = history.get('history', [])
                
                if not changes:
                    logger.info("No history changes found.")
                    return "OK"

                for change in changes:
                    messages_added = change.get('messagesAdded', [])
                    for record in messages_added:
                        message_id = record.get('message', {}).get('id')
                        if message_id:
                             logger.info(f"Processing message ID: {message_id}")
                             # 4. Get full message details
                             msg = service.users().messages().get(userId='me', id=message_id, format='full').execute()
                             process_single_message(service, msg)

            except Exception as e:
                logger.error(f"Error fetching history or messages: {e}")
            
        except json.JSONDecodeError:
            logger.error("Error decoding JSON from Pub/Sub message.")
    else:
        logger.warning("No data in Pub/Sub message.")

    return "OK"

def process_single_message(service, msg):
    """Parses email content and decides on action."""
    headers = msg.get('payload', {}).get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
    sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
    
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
    
    logger.info(f"Email from: {sender} | Subject: {subject}")
    
    # Always engage AI Agent (Trigger check removed)
    logger.info("Engaging AI Agent for all emails.")
     
    try:
        # Initialize Agent
        scenario = load_scenario(DEFAULT_SCENARIO_PATH)
        rubric = load_rubric(DEFAULT_RUBRIC_PATH)
        
        api_key = os.environ.get("OPENAI_API_KEY")
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
        
        # Build Prior Thread (Mocking context if needed, or fetching previous emails)
        # For this simple version, we assume the student is starting or we just treat it as a single turn.
        # Ideally, we should fetch the threadId key from Gmail to rebuild context.
        prior_thread = agent.build_starter_thread() 
        
        # Process interaction
        result = agent.evaluate_and_respond(
            prior_thread=prior_thread,
            student_email=student_email,
            rubric=rubric.items
        )
        
        # Send reply
        if result.counterpart_reply:
            logger.info(f"Generated response for {sender}. Sending reply.")
            # Build a nice reply that includes the feedback
            reply_body = (
                f"{result.counterpart_reply}\n\n"
                f"--- FEEDBACK ---\n"
                f"{result.grading.overall_comment}\n\n"
                f"Score: {result.grading.total_score}/{result.grading.max_total_score}"
            )
            send_reply(service, msg, reply_body)
        else:
            logger.info(f"No response generated for {sender}.")
            
    except Exception as e:
        logger.error(f"Error during AI processing: {e}")

def send_reply(service, original_msg, reply_text):
    """Sends a reply via Gmail API."""
    try:
        thread_id = original_msg['threadId']
        headers = original_msg['payload']['headers']
        subject = next(h['value'] for h in headers if h['name'] == 'Subject')
        
        # Prepare Message
        # Note: Proper MIME construction is better, but simple dictionary works for text
        message_content = f"To: {next(h['value'] for h in headers if h['name'] == 'From')}\r\n" \
                          f"Subject: Re: {subject}\r\n" \
                          f"In-Reply-To: {original_msg['id']}\r\n" \
                          f"References: {original_msg['id']}\r\n" \
                          f"\r\n" \
                          f"{reply_text}"
        
        raw_message = base64.urlsafe_b64decode(message_content.encode("utf-8")).decode("utf-8") # Wait, encoding to base64 for API
        raw_message = base64.urlsafe_b64encode(message_content.encode("utf-8")).decode("utf-8")
        
        body = {'raw': raw_message, 'threadId': thread_id}
        
        service.users().messages().send(userId='me', body=body).execute()
        logger.info("Reply sent successfully.")
        
    except Exception as e:
        logger.error(f"Error sending reply: {e}")

def get_gmail_service():
    """Builds Gmail service using environment variables."""
    # Build Gmail service using setup credentials in environment
    try:
        client_id = os.environ.get('GMAIL_CLIENT_ID')
        client_secret = os.environ.get('GMAIL_CLIENT_SECRET')
        refresh_token = os.environ.get('GMAIL_REFRESH_TOKEN')
        
        if not all([client_id, client_secret, refresh_token]):
            logger.error("Missing GMAIL OAuth environment variables.")
            return None

        creds = Credentials(
            None, # No access token initially
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        logger.error(f"Auth error: {e}")
        return None
