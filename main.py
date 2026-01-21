import base64
import json
import os
import logging
from pathlib import Path

import functions_framework
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from email_agent.scenario_loader import load_scenario
from email_agent.rubric_loader import load_rubric
from email_agent.email_agent import EmailAgent, EmailMessage

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants - Path resolution
# Note: email_agent/ directory structure is preserved in Cloud Functions deployment
BASE_DIR = Path(__file__).resolve().parent / "email_agent"
DEFAULT_SCENARIO_PATH = BASE_DIR / "scenarios/missed_remote_standup.json"
DEFAULT_RUBRIC_PATH = BASE_DIR / "rubrics/default.json"

# Canary log to verify logging is working in Cloud Functions
logger.info("PEB Service module loaded. Logging is operational.")

@functions_framework.cloud_event
def process_email(cloud_event):
    """
    Triggered from a message on a Cloud Pub/Sub topic.
    The message usually comes from Gmail push notifications.
    """
    logger.info("process_email triggered by Pub/Sub event")
    
    # 1. Decode the Pub/Sub message
    data = cloud_event.data
    pubsub_message = data.get("message", {})
    
    if "data" in pubsub_message:
        message_data = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        logger.debug(f"Received message data: {message_data}")
        
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

def process_single_message(service, msg):
    """Parses email content and decides on action."""
    try:
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
        
        logger.info(f"Processing Email - From: {sender} | Subject: {subject}")
        # logger.info(f"Body snippet: {body[:100]}...") # Optional: log body snippet
        
        # Guard: Don't reply to self or bots to avoid loops
        if "google" in sender.lower() or "bot" in sender.lower() or "noreply" in sender.lower():
             logger.info(f"Skipping auto-reply for likely bot/self: {sender}")
             return

        # Initialize Agent
        logger.info("Loading Scenario and Rubric...")
        scenario = load_scenario(DEFAULT_SCENARIO_PATH)
        rubric = load_rubric(DEFAULT_RUBRIC_PATH)
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("Missing OPENAI_API_KEY")
            return

        logger.info("Initializing EmailAgent...")
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
        logger.info("Calling agent.evaluate_and_respond (OpenAI)...")
        prior_thread = agent.build_starter_thread() 
        
        result = agent.evaluate_and_respond(
            prior_thread=prior_thread,
            student_email=student_email,
            rubric=rubric.items
        )
        
        logger.info(f"Agent finished. Reply generated: {bool(result.counterpart_reply)}")

        # Send reply
        if result.counterpart_reply:
            logger.info(f"Preparing to send reply to {sender}...")
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

def send_reply(service, original_msg, reply_text):
    """Sends a reply via Gmail API."""
    try:
        thread_id = original_msg['threadId']
        headers = original_msg['payload']['headers']
        subject = next(h['value'] for h in headers if h['name'] == 'Subject')
        
        sender_email = next((h['value'] for h in headers if h['name'] == 'From'), "")
        
        # Get the Message-ID from the original email for proper threading
        message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)
        
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

def get_gmail_service():
    """Builds Gmail service using OAuth credentials from environment variables."""
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
        logger.error(f"Auth error: {e}", exc_info=True)
        return None
