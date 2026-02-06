#!/usr/bin/env python3
"""
Check if Gmail watch is active for pathwayemailbot@gmail.com
"""
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Load bot token
with open('token.bot.secret.json') as f:
    token_data = json.load(f)

with open('config/client_config.secret.json') as f:
    client_config = json.load(f)
    client_id = client_config['installed']['client_id']
    client_secret = client_config['installed']['client_secret']

creds = Credentials(
    None,
    refresh_token=token_data['refresh_token'],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret
)

service = build('gmail', 'v1', credentials=creds)

# Get profile to check watch status
try:
    profile = service.users().getProfile(userId='me').execute()
    print(f"Email: {profile['emailAddress']}")
    print(f"Total messages: {profile['messagesTotal']}")
    print(f"History ID: {profile['historyId']}")
    print("\n✓ Connected to Gmail successfully")
except Exception as e:
    print(f"✗ Error connecting to Gmail: {e}")
    exit(1)

# Try to stop/start watch to see if it's active
PROJECT_ID = "pathway-email-bot-6543"
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/email-notifications"

print(f"\nSetting up watch for topic: {TOPIC_NAME}")

request = {
    'labelIds': ['INBOX'],
    'topicName': TOPIC_NAME
}

try:
    response = service.users().watch(userId='me', body=request).execute()
    print("\n✓ Gmail watch configured successfully!")
    print(f"  Expiration: {response.get('expiration')} (epoch ms)")
    print(f"  History ID: {response.get('historyId')}")
    
    # Convert expiration to human readable
    import datetime
    exp_ms = int(response.get('expiration'))
    exp_date = datetime.datetime.fromtimestamp(exp_ms / 1000)
    print(f"  Expires: {exp_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
except Exception as e:
    print(f"\n✗ Error setting up watch: {e}")
    exit(1)
