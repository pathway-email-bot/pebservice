# Future Improvements - Secrets Management

## Problem

Currently, Gmail OAuth tokens are:
- Stored in GitHub Secrets
- Deployed as environment variables to Cloud Functions
- **Not refreshed automatically** - they expire and require manual renewal
- Synced during deployment (not fetched at runtime)

This causes:
- Service outages when tokens expire
- Manual intervention required every time
- Security risk (tokens in multiple places)
- No centralized secret rotation

## Proposed Solution: Automated Token Refresh with Secret Manager

### Architecture

1. **Store refresh token in Google Secret Manager**
   - Single source of truth
   - IAM-controlled access
   - Automatic versioning

2. **Cloud Functions fetch secrets at runtime**
   - Use Workload Identity (no keys needed)
   - Always get latest token
   - No secrets in environment variables

3. **Automated token refresh**
   - **Option A**: GitHub Actions scheduled workflow (free tier: cron every 6 hours)
   - **Option B**: Cloud Scheduler + Cloud Function (minimal cost: ~$0.10/month)
   - **Option C**: Refresh token on-demand in Cloud Function (add caching)

### Implementation Plan

#### Phase 1: Move to Secret Manager

```python
# service/auth_utils.py
from google.cloud import secretmanager

def get_gmail_credentials():
    """Fetch Gmail OAuth credentials from Secret Manager at runtime"""
    client = secretmanager.SecretManagerServiceClient()
    
    # Fetch secrets
    client_id = client.access_secret_version(
        request={"name": "projects/pathway-email-bot-6543/secrets/gmail-client-id/versions/latest"}
    ).payload.data.decode("UTF-8")
    
    client_secret = client.access_secret_version(
        request={"name": "projects/pathway-email-bot-6543/secrets/gmail-client-secret/versions/latest"}
    ).payload.data.decode("UTF-8")
    
    refresh_token = client.access_secret_version(
        request={"name": "projects/pathway-email-bot-6543/secrets/gmail-refresh-token/versions/latest"}
    ).payload.data.decode("UTF-8")
    
    return {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token
    }
```

#### Phase 2: Automated Refresh (Option A - GitHub Actions)

```yaml
# .github/workflows/refresh-gmail-token.yaml
name: Refresh Gmail OAuth Token

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:  # Manual trigger

jobs:
  refresh-token:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Google Auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: '${{ secrets.GCP_SA_KEY }}'
      
      - name: Refresh OAuth Token
        run: |
          # Use refresh token to get new access token
          python scripts/refresh_gmail_token.py
```

```python
# scripts/refresh_gmail_token.py
from google.oauth2.credentials import Credentials
from google.cloud import secretmanager
import requests

def refresh_token():
    # Fetch refresh token from Secret Manager
    client = secretmanager.SecretManagerServiceClient()
    refresh_token = client.access_secret_version(
        request={"name": "projects/pathway-email-bot-6543/secrets/gmail-refresh-token/versions/latest"}
    ).payload.data.decode("UTF-8")
    
    # Exchange for new access token (this validates refresh token is still valid)
    response = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': os.environ['GMAIL_CLIENT_ID'],
        'client_secret': os.environ['GMAIL_CLIENT_SECRET'],
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    })
    
    if response.status_code == 200:
        print("✅ Refresh token is valid, no action needed")
    else:
        print("❌ Refresh token expired, manual re-authentication required")
        # Send alert (email, Slack, etc.)
```

#### Phase 3: Update Cloud Functions

**Remove environment variables from deployment:**
```yaml
# .github/workflows/deploy-service.yaml
- name: Deploy process_email to Cloud Functions (Gen 2)
  run: |
    gcloud functions deploy process_email \
      --gen2 \
      --region=us-central1 \
      --runtime=python311 \
      --source=service \
      --entry-point=process_email \
      --trigger-topic=email-notifications
      # No --set-env-vars needed! Fetched at runtime from Secret Manager
```

**Grant Secret Manager access to Cloud Functions:**
```bash
gcloud secrets add-iam-policy-binding gmail-refresh-token \
  --member="serviceAccount:pathway-email-bot-6543@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Benefits

- ✅ **Zero manual intervention** - tokens refresh automatically
- ✅ **More secure** - secrets in Secret Manager, not GitHub
- ✅ **Runtime flexibility** - rotate secrets without redeploying
- ✅ **Monitoring** - GitHub Actions logs show refresh attempts
- ✅ **Cost-effective** - GitHub Actions free tier sufficient

### Migration Steps

1. **Initial setup** (~30 min):
   - Create secrets in Secret Manager
   - Update auth_utils.py to fetch from Secret Manager
   - Test locally with `gcloud auth application-default login`

2. **Deploy with new auth** (~10 min):
   - Update Cloud Functions to use new auth code
   - Grant IAM permissions
   - Deploy and test

3. **Add automated refresh** (~20 min):
   - Create GitHub Actions workflow
   - Add refresh script
   - Test manual trigger

4. **Cleanup** (~5 min):
   - Remove secrets from GitHub Secrets (or keep as backup)
   - Update deployment workflows
   - Document in README

### Estimated Cost

- **Secret Manager**: $0.06/10k accesses (our volume: ~free)
- **GitHub Actions**: Free tier (2000 min/month, we need ~1 min/day)
- **Total**: Effectively **$0/month**

### Alternative: On-Demand Refresh in Cloud Functions

```python
# service/auth_utils.py
import time
from google.cloud import secretmanager

TOKEN_CACHE = {'access_token': None, 'expires_at': 0}

def get_gmail_service(email: str):
    """Get Gmail service with cached access token"""
    now = time.time()
    
    # Refresh if token expired or expiring soon
    if TOKEN_CACHE['expires_at'] < now + 300:  # 5 min buffer
        refresh_gmail_access_token()
    
    return build_service_with_token(TOKEN_CACHE['access_token'])

def refresh_gmail_access_token():
    """Refresh access token using refresh token from Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()
    refresh_token = client.access_secret_version(
        request={"name": "projects/pathway-email-bot-6543/secrets/gmail-refresh-token/versions/latest"}
    ).payload.data.decode("UTF-8")
    
    # Exchange for new access token
    response = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': get_secret('gmail-client-id'),
        'client_secret': get_secret('gmail-client-secret'),
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    })
    
    data = response.json()
    TOKEN_CACHE['access_token'] = data['access_token']
    TOKEN_CACHE['expires_at'] = time.time() + data['expires_in']
```

**Pros**: No external automation needed, tokens always fresh
**Cons**: Cold start latency, need to handle refresh failures

---

## Decision

Recommend **Phase 1 + Phase 3 (On-Demand Refresh)** for simplicity:
- Move secrets to Secret Manager
- Refresh tokens on-demand in Cloud Functions
- Phase 2 (GitHub Actions) optional for monitoring

This gives us automatic refresh with minimal complexity.

---

## Current Workaround (Manual)

Until this is implemented:
1. Run `scripts/get_token.py` for pathwayemailbot@gmail.com every ~7 days
2. Update GitHub Secrets manually
3. Redeploy Cloud Functions or wait for next deployment

---

**Priority**: Medium (service works but requires manual maintenance)  
**Effort**: ~1-2 hours (phases 1+3)  
**Impact**: High (eliminates manual token management)
