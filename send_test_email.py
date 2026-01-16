import base64
import time
from email.message import EmailMessage
from auth_utils import get_gmail_service

def send_test_email():
    """
    Sends a test email:
    FROM: 'personal' account (sender)
    TO: 'bot' account (recipient)
    """
    # 1. Get Sender Service (Personal)
    print("--- Authenticating SENDER (Personal) ---")
    sender_service = get_gmail_service(role='personal')
    if not sender_service:
        print("ERROR: Could not get 'personal' credentials.")
        return

    # 2. Get Recipient Address (Bot)
    # We authenticate as bot just to get its profile email, so we don't hardcode it (optional, but nice)
    print("\n--- Identifying RECIPIENT (Bot) ---")
    bot_service = get_gmail_service(role='bot')
    if not bot_service:
        print("ERROR: Could not get 'bot' credentials to identify address.")
        return
    
    bot_profile = bot_service.users().getProfile(userId='me').execute()
    bot_email = bot_profile['emailAddress']
    print(f"Target Bot Email: {bot_email}")

    # 3. Construct and Send Email
    sender_profile = sender_service.users().getProfile(userId='me').execute()
    sender_email = sender_profile['emailAddress']
    print(f"\nSending FROM: {sender_email} -> TO: {bot_email}")

    message = EmailMessage()
    message.set_content(
        "This is a test email sent by the pebservice verification script.\n"
        "It uses the 'personal' auth role to mimic a real student.\n\n"
        "Please reply if you receive this."
    )
    message["To"] = bot_email
    message["From"] = sender_email
    message["Subject"] = f"Automated Test Identity Split {int(time.time())}"

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {
        'raw': encoded_message
    }

    try:
        sent_message = sender_service.users().messages().send(userId="me", body=create_message).execute()
        print(f"\nSUCCESS: Test email sent! ID: {sent_message['id']}")
    except Exception as e:
        print(f"\nERROR: Failed to send email: {e}")

if __name__ == '__main__':
    send_test_email()
