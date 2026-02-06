# IAM Permissions Documentation

## Service Accounts

### Cloud Functions Service Account
Both Cloud Functions run as the default Compute Engine service account:
- **Account**: `687061619628-compute@developer.gserviceaccount.com`
- **Functions using this account**:
  - `process_email` (Pub/Sub triggered)
  - `send_scenario_email` (HTTP triggered)

### Required IAM Permissions

#### Secret Manager Access
The Cloud Functions need to read OAuth credentials from Secret Manager:

```bash
# Gmail Client ID
gcloud secrets add-iam-policy-binding gmail-client-id \
  --member="serviceAccount:687061619628-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Gmail Client Secret
gcloud secrets add-iam-policy-binding gmail-client-secret \
  --member="serviceAccount:687061619628-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Gmail Refresh Token (Bot Account)
gcloud secrets add-iam-policy-binding gmail-refresh-token-bot \
  --member="serviceAccount:687061619628-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

**Status**: ✅ Configured (2026-02-06)

#### Firestore Access
The service account needs read/write access to Firestore for:
- Reading scenario configurations
- Writing grading results
- Updating attempt status

**Default behavior**: Cloud Functions automatically have Firestore access via Firebase Admin SDK when deployed to the same project.

#### Pub/Sub Access
For `process_email` function to receive email notifications:
- **Topic**: `projects/pathway-email-bot/topics/gmail-notifications`
- **Subscription**: Auto-managed by Cloud Functions

**Default behavior**: Function deployment automatically creates and configures the subscription.

## Secrets Configuration

### Secrets in GCP Secret Manager
| Secret Name | Purpose | Used By |
|------------|---------|---------|
| `gmail-client-id` | OAuth 2.0 Client ID | Both functions |
| `gmail-client-secret` | OAuth 2.0 Client Secret | Both functions |
| `gmail-refresh-token-bot` | Refresh token for pathwayemailbot@gmail.com | Both functions |

### Secret References in Cloud Functions
Functions are configured to mount these secrets as environment variables:
- `GMAIL_CLIENT_ID` → `gmail-client-id:latest`
- `GMAIL_CLIENT_SECRET` → `gmail-client-secret:latest`
- `GMAIL_REFRESH_TOKEN` → `gmail-refresh-token-bot:latest`

## Deployment Commands

### Deploy with Secret Manager (Recommended)
```bash
# Secrets are auto-configured via GitHub Actions workflow
# Manual deployment:
gcloud functions deploy send_scenario_email \
  --gen2 \
  --region=us-central1 \
  --runtime=python311 \
  --source=./service \
  --entry-point=send_scenario_email \
  --trigger-http \
  --allow-unauthenticated
```

### Alternative: Deploy with Environment Variables
```bash
# If you want to bypass Secret Manager:
gcloud functions deploy send_scenario_email \
  --gen2 \
  --region=us-central1 \
  --runtime=python311 \
  --source=./service \
  --entry-point=send_scenario_email \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars="GMAIL_CLIENT_ID=...,GMAIL_CLIENT_SECRET=...,GMAIL_REFRESH_TOKEN=..."
```

**Note**: Cannot mix secret references and env vars for the same variable name.

## Verification

### Check Current IAM Bindings
```bash
# Check who can access a secret
gcloud secrets get-iam-policy gmail-client-id
gcloud secrets get-iam-policy gmail-client-secret
gcloud secrets get-iam-policy gmail-refresh-token-bot

# Check what service account a function uses
gcloud functions describe process_email --gen2 --region=us-central1 --format="value(serviceConfig.serviceAccountEmail)"
gcloud functions describe send_scenario_email --gen2 --region=us-central1 --format="value(serviceConfig.serviceAccountEmail)"
```

### Test Secret Access
```bash
# From within a Cloud Function, the secrets are available as env vars:
import os
print(os.environ.get('GMAIL_CLIENT_ID'))  # Should print the client ID
```

## Security Considerations

1. **Default Compute Service Account**: We're using the default Compute Engine service account, which is fine for this project but in production you might want a dedicated service account with minimal permissions.

2. **Secret Rotation**: OAuth refresh tokens should be rotated periodically. See [todo_some_other_day.md](../todo_some_other_day.md) for automation plans.

3. **Unauthenticated HTTP Function**: `send_scenario_email` allows unauthenticated access because Firebase Auth validation happens in the function code, not at the Cloud Functions level.

4. **Least Privilege**: The service account only has access to the three Gmail secrets. Firestore access is implicitly granted via Firebase Admin SDK.

## Troubleshooting

### "Permission denied on secret"
- **Cause**: Service account lacks `roles/secretmanager.secretAccessor`
- **Fix**: Run the IAM binding commands above

### "Secret environment variable overlaps non secret environment variable"
- **Cause**: Trying to use both `--set-env-vars` and secret references for the same var
- **Fix**: Choose one method - either delete the function and redeploy, or update the function config

### "Service account not found"
- **Cause**: The project number might have changed or wrong project selected
- **Fix**: Verify with `gcloud config get-value project` and check project number in GCP Console
