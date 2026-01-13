import os
import json
import subprocess
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def set_gh_secret(name, value):
    try:
        # Use stdin to avoid leaking in process list, though body is okay for local
        subprocess.run(['gh', 'secret', 'set', name, '--body', value], check=True)
        print(f"✓ Set {name}")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to set {name}: {e}")

def main():
    if not os.path.exists('client_secret.json'):
        print("ERROR: 'client_secret.json' not found.")
        return

    # 1. Parse and Set Client Secrets
    with open('client_secret.json', 'r') as f:
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
    flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    print("\nAuthenticated!")
    
    # 3. Set Refresh Token
    if creds.refresh_token:
        print("Setting Refresh Token in GitHub...")
        set_gh_secret('GMAIL_REFRESH_TOKEN', creds.refresh_token)
        print("\nAll secrets set successfully!")
    else:
        print("\nWARNING: No refresh token returned. You might need to revoke access and try again to prompt for content.")

if __name__ == '__main__':
    main()
