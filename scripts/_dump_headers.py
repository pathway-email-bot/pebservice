"""Dump all headers from latest bot emails to a file."""
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

with open('client_config.secret.json') as f:
    cfg = json.load(f)['installed']
with open('token.bot.secret.json') as f:
    tok = json.load(f)

creds = Credentials(
    None,
    refresh_token=tok['refresh_token'],
    token_uri='https://oauth2.googleapis.com/token',
    client_id=cfg['client_id'],
    client_secret=cfg['client_secret']
)
service = build('gmail', 'v1', credentials=creds)

with open('test_logs/headers_dump.txt', 'w') as out:
    response = service.users().messages().list(userId='me', maxResults=3).execute()
    for msg_meta in response.get('messages', []):
        msg = service.users().messages().get(userId='me', id=msg_meta['id'], format='full').execute()
        headers = msg.get('payload', {}).get('headers', [])
        out.write(f"\n=== Message {msg_meta['id']} ===\n")
        out.write(f"Header count: {len(headers)}\n")
        for h in headers:
            out.write(f"  [{h['name']}]: {h['value'][:120]}\n")
        out.write("\n")
    out.write("Done.\n")

print("Written to test_logs/headers_dump.txt")
