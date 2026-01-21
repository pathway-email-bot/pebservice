import os
from auth_utils import get_gmail_service

def setup_watch():
    service = get_gmail_service(role='bot')
    if not service:
        print("Failed to obtain 'bot' credentials. Exiting.")
        return

    project_id = "pathway-email-bot-6543"
    topic_name = f"projects/{project_id}/topics/email-notifications"

    request = {
        'labelIds': ['INBOX'],
        'topicName': topic_name
    }

    try:
        response = service.users().watch(userId='me', body=request).execute()
        print("\nSUCCESS: Successfully set up Gmail watch for 'bot' account!")
        print(f"Expiration: {response.get('expiration')}")
        print(f"History ID: {response.get('historyId')}")
    except Exception as e:
        print(f"Error: Failed to set up Gmail watch: {e}")

if __name__ == '__main__':
    setup_watch()
