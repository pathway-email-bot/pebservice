# Deployment & Secrets Management Strategy

**Last Updated**: 2026-02-06

## Overview

This document explains our deployment architecture, service accounts, secrets management, and the rationale behind our IAM permission choices.

## Current State

### Deployment Architecture

We have **3 separate deployments**:

1. **Portal** (Frontend)
   - **Target**: GitHub Pages
   - **Trigger**: Push to `main` with changes in `portal/**`
   - **Deploy method**: GitHub Actions builds Vite app and pushes to `gh-pages` branch
   - **Auth**: Uses GitHub token (automatic)
   - **Status**: ✅ Working

2. **process_email** (Cloud Function Gen 2)
   - **Target**: GCP Cloud Functions
   - **Trigger**: Pub/Sub (gmail-notifications topic)
   - **Deploy method**: GitHub Actions using service account
   - **Auth**: Service account key in `GCP_SA_KEY` secret
   - **Status**: ⚠️ Needs verification

3. **send_scenario_email** (Cloud Function Gen 2)
   - **Target**: GCP Cloud Functions
   - **Trigger**: HTTP (called by portal)
   - **Deploy method**: GitHub Actions using service account
   - **Auth**: Service account key in `GCP_SA_KEY` secret
   - **Status**: ❌ Failing with IAM permission error

---

## Service Accounts in Play

### 1. Runtime Service Account (Cloud Functions execution)
- **Account**: `687061619628-compute@developer.gserviceaccount.com`
- **Purpose**: Runs the Cloud Functions code
- **Permissions**:
  - ✅ `roles/secretmanager.secretAccessor` on gmail secrets (manually granted today)
  - ✅ Firestore access (automatic via Firebase Admin SDK)
  - ✅ Pub/Sub subscriber (automatic for triggered function)
- **Status**: Working correctly

### 2. Deployment Service Account (GitHub Actions)
- **Account**: `peb-service-account@pathway-email-bot-6543.iam.gserviceaccount.com`
- **Purpose**: Deploy functions from GitHub Actions
- **Current Permissions**:
  - ✅ `roles/logging.logWriter` (from setup_infra.ps1)
  - ✅ `roles/pubsub.subscriber` (from setup_infra.ps1)
  - ✅ `roles/cloudfunctions.developer` (just granted)
  - ✅ `roles/artifactregistry.writer` (appears in IAM output)
  - ✅ `roles/iam.serviceAccountUser` (appears in IAM output)
  - ✅ `roles/pubsub.editor` (appears in IAM output)
- **Missing Permission**: `roles/run.admin` or `run.services.setIamPolicy`
- **Status**: ❌ Cannot deploy HTTP functions with `--allow-unauthenticated`

---

## Secrets Management Strategy

### Two-Tier System

**GitHub Secrets** (Long-lived, manually updated):
| Secret | Purpose | Updated |
|--------|---------|---------|
| `GCP_SA_KEY` | Service account key JSON for deployment | Initial setup |

**GCP Secret Manager** (Source of truth for runtime secrets):
| Secret | Purpose | Updated |
|--------|---------|---------|
| `gmail-client-id` | OAuth client ID | 2026-02-06 via sync_secrets.py |
| `gmail-client-secret` | OAuth client secret | 2026-02-06 via sync_secrets.py |
| `gmail-refresh-token-bot` | Refresh token | 2026-02-06 via get_token.py |
| `openai_api_key` | OpenAI API key | 2026-02-06 |

### Current Deployment YAML Strategy

```yaml
# All runtime secrets: Using GCP Secret Manager (✅ Best practice)
--set-secrets="GMAIL_CLIENT_ID=gmail-client-id:latest,GMAIL_CLIENT_SECRET=gmail-client-secret:latest,GMAIL_REFRESH_TOKEN=gmail-refresh-token-bot:latest,OPENAI_API_KEY=openai_api_key:latest"
```

**Benefits:**
- Single source of truth for all runtime secrets
- Consistent secret rotation workflow
- IAM-based access control
- Can use `scripts/sync_secrets.py` for management

---

## The Current Problem

### Error
```
ERROR: status=[403], code=[], message=[Permission 'run.services.setIamPolicy' 
denied on resource 'projects/pathway-email-bot-6543/locations/us-central1/
services/send-scenario-email']
```

### Root Cause
Cloud Functions Gen 2 runs on Cloud Run. The `--allow-unauthenticated` flag modifies the IAM policy on the underlying Cloud Run service to allow public invocations. The deployment service account (`peb-service-account`) needs permission to modify IAM policies.

### Why It Worked Manually
When I deployed manually, I was authenticated as `MichaelTReynolds@gmail.com` which has `roles/owner` on the project, so I could set IAM policies.

---

## Solution Options

### Option 1: Grant Cloud Run Admin (Broad)
```bash
gcloud projects add-iam-policy-binding pathway-email-bot-6543 \
  --member="serviceAccount:peb-service-account@pathway-email-bot-6543.iam.gserviceaccount.com" \
  --role="roles/run.admin"
```

**Pros**:
- ✅ Simple, one role
- ✅ Covers all Cloud Run operations
- ✅ Standard approach for CI/CD

**Cons**:
- ⚠️ Broad permissions (can manage all Cloud Run services)
- ⚠️ Could be over-privileged for what we need

**Recommended**: ✅ Yes, this is the standard approach

### Option 2: Grant Specific IAM Permission (Narrow)
```bash
# Create custom role with just run.services.setIamPolicy
# More complex, rarely needed in practice
```

**Pros**:
- ✅ Least privilege

**Cons**:
- ❌ More complex to maintain
- ❌ Need to update if we add more Cloud Run features

**Recommended**: ❌ Overkill for this use case

### Option 3: Don't Use --allow-unauthenticated (Change Architecture)
Remove `--allow-unauthenticated` flag and validate Firebase tokens at Cloud Functions level (which we already do).

**Pros**:
- ✅ Don't need IAM permission
- ✅ Defense in depth (two layers of auth)

**Cons**:
- ❌ More complex invocation (need to handle 401s properly)
- ❌ Extra latency (Cloud Run auth check before our auth check)
- ❌ Our code already validates Firebase tokens, so this is redundant

**Recommended**: ❌ Adds complexity without security benefit

---

## Solution Applied: Grant Cloud Run Admin

**Status**: ✅ Implemented (2026-02-06)

### Justification
1. **Standard practice**: CI/CD deploying Cloud Functions Gen 2 requires Cloud Run permissions
2. **Principle of least privilege**: Service account only used for deployment, not runtime
3. **Scope limited**: Only affects Cloud Run services, not other GCP resources
4. **Matches our needs**: We deploy HTTP functions with public endpoints

### Final IAM Configuration

**peb-service-account** (Deployment):
- `roles/cloudfunctions.developer` - Deploy Cloud Functions
- `roles/run.admin` - Manage Cloud Run services (including IAM policies)
- `roles/iam.serviceAccountUser` - Act as runtime service account
- `roles/artifactregistry.writer` - Push container images
- `roles/pubsub.editor` - Configure Pub/Sub triggers
- `roles/logging.logWriter` - Write deployment logs

**687061619628-compute** (Runtime):
- `roles/secretmanager.secretAccessor` on gmail-client-id, gmail-client-secret, gmail-refresh-token-bot
- Firestore access via Firebase Admin SDK (automatic)
- Pub/Sub subscription access (automatic)

---

## GitHub Secrets Cleanup

Orphaned secrets removed after migrating to GCP Secret Manager:
- ❌ `GMAIL_CLIENT_ID` - Now in Secret Manager
- ❌ `GMAIL_CLIENT_SECRET` - Now in Secret Manager  
- ❌ `GMAIL_REFRESH_TOKEN` - Now in Secret Manager
- ❌ `OPENAI_API_KEY` - Now in Secret Manager
- ❌ `GMAIL_TEST` - Old test secret
- ❌ `GMAIL_REF_TEST` - Old test secret

Remaining secrets (still needed):
- ✅ `GCP_SA_KEY` - Deployment service account key (only secret left!)

---

## Future Improvements

See [todo_some_other_day.md](current_working/todo_some_other_day.md):
1. Workload Identity Federation (eliminate GCP_SA_KEY)
2. Automated Gmail OAuth token refresh
3. Infrastructure as Code with Terraform
