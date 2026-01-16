import os
import json
import subprocess
from google_auth_oauthlib.flow import InstalledAppFlow

# Updated file names
CLIENT_CONFIG_FILE = 'client_config.secret.json'
TOKEN_FILE = 'token.secret.json'

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic'
]

def set_gh_secret(name, value):
    try:
        subprocess.run(['gh', 'secret', 'set', name, '--body', value], check=True)
        print(f"✓ Set {name}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to set {name}: {e}")

def main():
    if not os.path.exists(CLIENT_CONFIG_FILE):
        print(f"ERROR: '{CLIENT_CONFIG_FILE}' not found.")
        return

    # 1. Parse and Set Client Secrets
    with open(CLIENT_CONFIG_FILE, 'r') as f:
        data = json.load(f)
        installed = data.get('installed', {})
        client_id = installed.get('client_id')
        client_secret = installed.get('client_secret')
        
        if client_id and client_secret:
            print("Setting Client ID and Secret in GitHub...")
            set_gh_secret('GMAIL_CLIENT_ID', client_id)
            set_gh_secret('GMAIL_CLIENT_SECRET', client_secret)
        else:
            print("Could not parse client_id/secret from JSON.")

    # 2. Auth Flow
    print("\nStarting OAuth Flow...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_CONFIG_FILE, SCOPES)
    creds = flow.run_local_server(port=0, prompt='consent')
    
    print("\nAuthenticated!")
    
    # 3. Set Refresh Token
    if creds.refresh_token:
        token = creds.refresh_token
        print(f"\nGMAIL_REFRESH_TOKEN={token}")
        
        # Save as JSON
        with open(TOKEN_FILE, 'w') as f:
            json.dump({"refresh_token": token}, f)
        print(f"✓ Saved refresh token to {TOKEN_FILE}")
        
        print("Setting Refresh Token in GitHub...")
        set_gh_secret('GMAIL_REFRESH_TOKEN', token)
        print("\nAll secrets set successfully!")
    else:
        print(f"\nExisting Refresh Token (might be none): {creds.refresh_token}")
        print("\nWARNING: No refresh token returned.")

if __name__ == '__main__':
    main()
