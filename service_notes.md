# Service Notes: PEB Service

The goal of this service is to provide instant and highly reliable service while minimizing costs. The system is designed to be **virtually free** for ~100 invocations per month.

## Google Cloud Resources

All resources are hosted in project **`pathway-email-bot-6543`**.

| Resource | Name / Value | Description |
|:---|:---|:---|
| **Pub/Sub Topic** | `email-notifications` | Receives Gmail push notifications |
| **Pub/Sub Subscription** | `eventarc-us-central1-process-email-479061-sub-493` | Eventarc-managed, triggers Cloud Function |
| **Cloud Function** | `process_email` | Core AI logic and email handler |
| **Cloud Function** | `send_scenario_email` | HTTP endpoint for sending scenario starter emails |
| **Firestore Database** | `(default)` | Stores user attempts, active scenarios, and grading results |
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

## Firestore Database

**Location**: `us-central` (same region as Cloud Functions)

### Data Structure

```
users/{email}/
  ├── activeScenario: {scenarioId, attemptId, startedAt}
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

- **Portal**: Creates attempts when user clicks "Start" on a scenario
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
The Gmail API uses push notifications via `users.watch()`. This must be renewed every 7 days. Use `setup_watch.py` to configure or renew the watch on `pathwayemailbot@gmail.com`.

## Secret Management Strategy

**GCP Secret Manager is the source of truth** for all secrets. GitHub Secrets are a shadow copy used only for CI/CD.

### Secrets in GCP Secret Manager
| Secret Name | Description |
|:---|:---|
| `gmail-client-id` | OAuth Client ID |
| `gmail-client-secret` | OAuth Client Secret |

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

## Local Development

## Local Development

### 1. Setting up Gmail Watch (Local)
To receive push notifications or renew the watch locally:

1.  **Prerequisites**:
    - Ensure you have `client_config.secret.json` (formerly `client_secret.json`) in the root directory.
    
2.  **Run Setup**: 
    ```powershell
    python setup_watch.py
    ```
    - The script will automatically check for credentials.
    - If environment variables are set, it uses those.
    - If not, it looks for `token.secret.json`.
    - If missing, it will launch the browser for you to login and save the token to `token.secret.json`.

### 2. Local Debugging
To test the AI agent logic without deploying or sending real emails:
1. Ensure `OPENAI_API_KEY` is set in your environment.
2. Run the debug script:
   ```powershell
   python local_debug_user_email.py
   ```

### Secret Management
- **Naming Convention**: All files containing secrets must follow the pattern `*.secret.*` (e.g., `client_config.secret.json`, `token.secret.json`).
- **Git**: These files are globally ignored by `.gitignore`.

