#!/usr/bin/env python3
"""Test the Cloud Function main.py locally."""

import os
import sys
import json
import base64
from pathlib import Path

# Add service directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'service'))

# Mock the Cloud Event for testing
class MockCloudEvent:
    def __init__(self, data):
        self.data = data

def test_process_email():
    """Test process_email function with mocked Pub/Sub message."""
    
    # Load credentials from local files
    with open('config/client_config.secret.json') as f:
        client_config = json.load(f)
        client_id = client_config['installed']['client_id']
        client_secret = client_config['installed']['client_secret']
    
    with open('token.bot.secret.json') as f:
        token_data = json.load(f)
        refresh_token = token_data['refresh_token']
    
    # Set environment variables (same as Cloud Function)
    os.environ['GMAIL_CLIENT_ID'] = client_id
    os.environ['GMAIL_CLIENT_SECRET'] = client_secret
    os.environ['GMAIL_REFRESH_TOKEN'] = refresh_token
    os.environ['OPENAI_API_KEY'] = 'sk-test-fake-key'  # Not needed for this test
    
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {client_secret[:20]}...")
    print(f"Refresh Token: {refresh_token[:30]}...")
    
    # Import after setting environment variables
    from main import process_email
    
    # Create a mock Pub/Sub message (simulating Gmail watch notification)
    gmail_notification = {
        "emailAddress": "pathwayemailbot@gmail.com",
        "historyId": "5359"  # From our check_watch.py output
    }
    
    # Encode it like Pub/Sub does
    encoded_data = base64.b64encode(json.dumps(gmail_notification).encode()).decode()
    
    # Create mock cloud event
    cloud_event = MockCloudEvent({
        "message": {
            "data": encoded_data
        }
    })
    
    print("\n" + "="*60)
    print("Testing process_email function...")
    print("="*60 + "\n")
    
    try:
        result = process_email(cloud_event)
        print(f"\n✓ Success! Result: {result}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(test_process_email())
