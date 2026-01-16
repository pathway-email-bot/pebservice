import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# File Constants
CLIENT_CONFIG_FILE = 'client_config.secret.json'

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]

def get_token_filename(role: str) -> str:
    """Returns the token filename for a given role (e.g., 'bot', 'personal')."""
    return f"token.{role}.secret.json"

def get_creds_interactive(role: str):
    """Runs the OAuth flow to get fresh credentials for a specific role."""
    if not os.path.exists(CLIENT_CONFIG_FILE):
        print(f"ERROR: '{CLIENT_CONFIG_FILE}' not found. Cannot start auth flow.")
        return None

    print(f"\nStarting interactive OAuth Flow for role: '{role}'...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_CONFIG_FILE, SCOPES)
    creds = flow.run_local_server(port=0, prompt='consent')
    
    if creds and creds.refresh_token:
        # Save credentials
        token_file = get_token_filename(role)
        data = {"refresh_token": creds.refresh_token}
        with open(token_file, 'w') as f:
            json.dump(data, f)
        print(f"✓ Saved refresh token for '{role}' to {token_file}")
        return creds
    else:
        print("WARNING: Auth flow finished but no refresh token returned.")
        return creds

def get_credentials(role: str):
    """Resolves credentials from Local Token File -> Interactive Flow."""
    token_file = get_token_filename(role)

    # 1. Try Local Token File
    if os.path.exists(token_file) and os.path.exists(CLIENT_CONFIG_FILE):
        print(f"Checking {token_file} for '{role}' credentials...")
        try:
            with open(token_file, 'r') as f:
                content = f.read().strip()
                try:
                    data = json.loads(content)
                    refresh_token = data.get("refresh_token")
                except json.JSONDecodeError:
                    # Legacy support if user manually pasted valid json-like string or old format
                    # But for this new system, we expect JSON.
                    print(f"Warning: {token_file} is not valid JSON. Ignoring.")
                    refresh_token = None
            
            # Load Client Config
            with open(CLIENT_CONFIG_FILE, 'r') as f:
                 client_data = json.load(f)
                 installed = client_data.get('installed', {})
                 client_id = installed.get('client_id')
                 client_secret = installed.get('client_secret')

            if refresh_token and client_id and client_secret:
                print(f"Using local secret file for '{role}'.")
                return Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    client_id=client_id,
                    client_secret=client_secret,
                    token_uri="https://oauth2.googleapis.com/token"
                )
        except Exception as e:
            print(f"Error reading local secrets: {e}")

    # 2. Interactive Fallback
    print(f"No valid credentials found for '{role}'. Launching browser to authenticate...")
    return get_creds_interactive(role)

def get_gmail_service(role: str):
    """Returns a Gmail service instance for the specified role."""
    creds = get_credentials(role)
    if not creds:
        return None
    return build('gmail', 'v1', credentials=creds)
