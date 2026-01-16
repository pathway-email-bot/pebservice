import os
import google.auth
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def setup_watch():
    # Load credentials from environment variables (like the Cloud Function does)
    creds = Credentials(
        token=None,  # Not needed for refresh
        refresh_token=os.environ.get('GMAIL_REFRESH_TOKEN'),
        client_id=os.environ.get('GMAIL_CLIENT_ID'),
        client_secret=os.environ.get('GMAIL_CLIENT_SECRET'),
        token_uri="https://oauth2.googleapis.com/token"
    )

    service = build('gmail', 'v1', credentials=creds)

    # Note: Ensure this matches the project created in setup_infra.ps1
    # or pass it as an environment variable/argument.
    project_id = os.environ.get("GCP_PROJECT_ID", "pathway-email-bot-6543")
    topic_name = f"projects/{project_id}/topics/email-notifications"

    request = {
        'labelIds': ['INBOX'],
        'topicName': topic_name
    }

    try:
        response = service.users().watch(userId='me', body=request).execute()
        print("Success: Successfully set up Gmail watch!")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: Failed to set up Gmail watch: {e}")

if __name__ == '__main__':
    # Add a check for environment variables
    missing = [v for v in ['GMAIL_REFRESH_TOKEN', 'GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET'] if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
    else:
        setup_watch()
