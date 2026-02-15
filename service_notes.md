# Service Notes: PEB Service

The goal of this service is to provide instant and highly reliable service while minimizing costs. The system is designed to be **virtually free** for ~100 invocations per month.

## Google Cloud Resources

All resources are hosted in project **`pathway-email-bot-6543`**.

| Resource | Name / Value | Description |
|:---|:---|:---|
| **Pub/Sub Topic** | `email-notifications` | Receives Gmail push notifications |
| **Pub/Sub Subscription** | `eventarc-us-central1-process-email-479061-sub-493` | Eventarc-managed, triggers Cloud Function |
| **Cloud Function** | `process_email` | Core AI logic and email handler (**512Mi memory required**) |
| **Cloud Function** | `start_scenario` | HTTP endpoint for starting scenarios |
| **Firestore Database** | `pathway` | Stores user attempts, active scenarios, and grading results |
| **Service Account** | `687061619628-compute@developer.gserviceaccount.com` | Default Compute SA used by functions |
| **AI Model** | `gpt-4o` (OpenAI) | LLM for grading and responses |
| **Secret Manager** | `gmail-client-id`, `gmail-client-secret`, `gmail-refresh-token-bot`, `openai-api-key` | OAuth credentials and API keys |
| **GitHub Pages** | `https://pathway-email-bot.github.io/pebservice/` | Student portal (Vite + TypeScript) |

### Required APIs
- `gmail.googleapis.com` - Read/send emails
- `cloudfunctions.googleapis.com` - Cloud Functions
- `pubsub.googleapis.com` - Pub/Sub messaging
- `run.googleapis.com` - Cloud Run (Gen 2 functions)
- `cloudbuild.googleapis.com` - Build and deploy
- `secretmanager.googleapis.com` - Secret Manager
- `firestore.googleapis.com` - Firestore database

## Service Accounts & IAM

*Last audited: 2026-02-14*

| Service Account | Purpose | Roles | Key / Auth |
|---|---|---|---|
| `peb-deployer@…` | **CI/CD deploy** — deploys Cloud Functions from GitHub Actions | `cloudfunctions.developer`, `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser`, `logging.logWriter`, `pubsub.editor`, `pubsub.subscriber` | `deployer-key.secret.json` / GitHub secret `GCP_DEPLOYER_KEY` |
| `peb-test-runner@…` | **Integration tests** — used by both CI and local dev | `secretmanager.secretAccessor`, `datastore.user`, `datastore.owner`*, `cloudfunctions.viewer` | `test-runner-key.secret.json` (local) / SA impersonation (CI) |
| `peb-runtime@…` | **Cloud Function runtime** — identity both functions run as | `secretmanager.secretAccessor`, `datastore.user`, `datastore.owner`* | Automatic (GCP metadata server) |
| `firebase-adminsdk-fbsvc@…` | Firebase Admin SDK agent (**Google-managed, do not modify**) | `firebase.sdkAdminServiceAgent`, `firebaseauth.admin`, `iam.serviceAccountTokenCreator` | — |
| `service-687061619628@gcp-sa-pubsub.iam.gserviceaccount.com` | **Pub/Sub service agent** — invokes `process-email` Cloud Run service | `run.invoker` on `process-email` service | — (Google-managed) |

\* `datastore.owner` is required because the `pathway` database is a named database (not `(default)`). `datastore.user` alone is insufficient — GCP IAM quirk. See todo.md.

> [!CAUTION]
> The Pub/Sub service agent's `run.invoker` binding can be **silently dropped** when redeploying functions or changing SA roles. If `process_email` stops processing emails, check this binding first.

### Credential Discovery (ADC)

Google client libraries check credentials in order: `GOOGLE_APPLICATION_CREDENTIALS` env var → `gcloud auth application-default login` → GCP metadata server.

| Environment | Identity | How |
|---|---|---|
| **Cloud Functions** | `peb-runtime@…` | Metadata server (automatic) |
| **GitHub Actions — deploy** | `peb-deployer@…` | `google-github-actions/auth` sets env var |
| **GitHub Actions — tests** | `peb-test-runner@…` | `peb-deployer` impersonates via `serviceAccountTokenCreator` |
| **Local — tests** | `peb-test-runner@…` | `tests/conftest.py` auto-discovers `test-runner-key.secret.json` |

## Firestore Database

**Location**: `us-central` (same region as Cloud Functions)
**Database name**: `pathway` (named database, NOT `(default)`)

> **⚠️ Named Database Note**: Using a named database (`pathway`) instead of `(default)` adds IAM
> complexity — `roles/datastore.user` alone is insufficient; `roles/datastore.owner` is also needed.
> This has caused repeated permission issues. Consider migrating to `(default)` if the project
> only ever needs one database (see todo.md).

### Data Structure

```
users/{email}/
  ├── activeScenarioId: string          # currently active scenario
  ├── activeAttemptId: string           # currently active attempt
  └── attempts/{attemptId}/
      ├── scenarioId: string
      ├── status: "pending" | "awaiting_student_email" | "graded"
      ├── startedAt: timestamp
      ├── score: number (null until graded)
      ├── maxScore: number (null until graded)
      └── feedback: string (null until graded)
```

### Setup

**Initial creation** must be done through Firebase Console (gcloud CLI doesn't support first-time database creation):
1. Visit: https://console.firebase.google.com/project/pathway-email-bot-6543/firestore
2. Click "Create Database"
3. Select **Production mode** (for security rules)
4. Choose location: **us-central** (match Cloud Functions region)

### Usage

- **start_scenario**: Creates attempts when user clicks "Start" on a scenario
- **process_email**: Queries active scenario to match incoming emails, updates with grading results
- **Portal**: Displays grading results in drawer after email exchange

### Security Rules

Security rules are defined in `firestore.rules` and enforce that:
- Users can only read/write their own data (authenticated by email)
- Cloud Functions use service account credentials (bypass security rules)

Deploy rules:
```powershell
firebase deploy --only firestore:rules
```

### Gmail Watch Configuration
The Gmail API uses push notifications via `users.watch()`. The watch expires every 7 days but is **automatically renewed** by the `_ensure_watch()` function in `main.py`. This uses a Firestore transaction to prevent multiple instances from renewing simultaneously.

- **Watch status**: stored in Firestore at `system/watch_status`
- **Renewal trigger**: any call to `start_scenario` checks and renews if needed
- **Manual renewal**: no longer needed (previously required `setup_watch.py`)

### OAuth Consent Screen & Token Expiration
- **Status**: Published to **Production** (as of 2026-02-12)
- **User Type**: External (required for consumer Gmail accounts)
- **Effect**: Refresh tokens no longer expire after 7 days
- **Token validity**: Refresh tokens remain valid indefinitely unless:
  - User explicitly revokes access
  - Token unused for 6 months (won't happen — email watch keeps it active)
  - Bot account password is changed
- **Console**: [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent?project=pathway-email-bot-6543)

## Secret Management Strategy

**GCP Secret Manager is the source of truth** for all secrets. GitHub Secrets are a shadow copy used only for CI/CD.

### Secrets in GCP Secret Manager
| Secret Name | Format | Description |
|:---|:---|:---|
| `gmail-client-id` | Plain string | OAuth Client ID |
| `gmail-client-secret` | Plain string | OAuth Client Secret |
| `gmail-refresh-token-bot` | **JSON** | OAuth refresh token for pathwayemailbot@gmail.com (permanent, regenerated 2026-02-12) |
| `gmail-refresh-token-test` | **JSON** | OAuth refresh token for michaeltreynolds.test@gmail.com (test account) |
| `openai-api-key` | Plain string | OpenAI API key for AI grading |

> **Secret Format Details**: Refresh token secrets are stored as JSON by `get_token.py`:
> ```json
> {"refresh_token": "1//06...", "generated_at": "2026-...", "role": "bot", "email": "..."}
> ```
> The Cloud Function (`main.py:get_gmail_service`) parses this JSON to extract `refresh_token`.
> All other secrets are stored as plain strings. All values are `.strip()`'d on read.

### Syncing Secrets

```powershell
# Sync from GCP to local dev
python sync_secrets.py

# Sync from GCP to both local and GitHub
python sync_secrets.py --github

# List all secrets in GCP
python sync_secrets.py --list
```

### GitHub Secrets (Shadow Copy)
These are synced FROM GCP Secret Manager using `sync_secrets.py --github`:
### Setup Flow & Token Generation
To set up or refresh your credentials:
1. **GCP Setup**: 
   - Enable Gmail, Cloud Functions, Pub/Sub, and Cloud Build APIs.
   - Create a **Desktop app** OAuth client to get the Client ID and Secret.
2. **Local Auth**:
   - Use `get_token.py` to perform the OAuth flow.
   - Run `python get_token.py`. This will open a browser to authorize the bot's Gmail account and save the refresh token to `token_capture.txt` (which is git-ignored).
3. **Set Secrets**:
   - Use the `gh` CLI or the script itself to push these to GitHub Secrets.
### Infrastructure Deployment
Use `setup_infra.ps1` to create the project, enable APIs, and configure the service account and topics.
### Actions
- Deployment workflows should use the `google-github-actions/auth` for secure authentication.
- Monitor workflow runs via `gh run list`.

## Deployment

```powershell
# Deploy process_email (must include --memory=512Mi)
gcloud functions deploy process_email --gen2 --region=us-central1 --runtime=python311 --source=service --entry-point=process_email --trigger-topic=email-notifications --memory=512Mi --project=pathway-email-bot-6543
```

> **Note**: Default memory (256Mi) causes OOM — the OpenAI SDK + Gmail API + Firebase Admin + Secret Manager require ~300-400 MiB at runtime.

## Local Development

### Scripts (`scripts/`)

| Script | Purpose |
|---|---|
| `auth_utils.py` | Shared OAuth utility — builds Gmail credentials from local token files |
| `get_token.py` | Interactive OAuth flow → stores refresh token in Secret Manager + local file |
| `sync_secrets.py` | Syncs secrets from GCP Secret Manager to local `client_config.secret.json` and optionally GitHub |
| `setup_gcloud.ps1` | One-time GCP project setup (APIs, service accounts) |
| `setup_infra.ps1` | One-time infrastructure setup (Pub/Sub, Cloud Functions) |
| `setup_venv.ps1` | Python venv setup for local development |

### Secret Management
- **Naming Convention**: All files containing secrets must follow the pattern `*.secret.*` (e.g., `client_config.secret.json`, `token.bot.secret.json`).
- **Git**: These files are globally ignored by `.gitignore`.
- **Token files**: `token.bot.secret.json` and `token.test.secret.json` live in the repo root.

