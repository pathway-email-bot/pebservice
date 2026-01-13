# Service Notes: PEB Service

The goal of this service is to provide instant and highly reliable service while minimizing costs. The system is designed to be **virtually free** for ~100 invocations per month.

## Google Cloud Resources
All cloud resources will be created in the `pathway-email-bot` (or TBD) project.

| Resource Type | Placeholder/Name | Description | Est. Cost / 1k Interactions |
| :--- | :--- | :--- | :--- |
| **GCP Project** | `pathway-email-bot-6543` | Main project hosting all resources. | $0.00 |
| **Gmail API** | `Enabled` | Must be enabled for the service account. | $0.00 |
| **Pub/Sub Topic** | `email-notifications` | Receives push notifications from Gmail. | ~$0.00 |
| **Pub/Sub Subscription** | `[CF_PUSH_SUBSCRIPTION]` | Triggers the Cloud Function. | ~$0.00 |
| **Cloud Function** | `process_email` | The core AI logic and email handler. | ~$0.10 - $0.50 |
| **Service Account** | `peb-service-account` | Credentials used by the Cloud Function. | $0.00 |
| **AI Model API** | `[AI_MODEL_NAME]` | LLM for generating responses. | $0.50 - $2.00* |

*\*Costs vary based on model choice and token usage.*

## GitHub Configuration
### Secrets
Manage these via `gh secret set`:
- `GCP_PROJECT_ID`: ID of the Google Cloud Project.
- `GCP_SA_KEY`: JSON service account key for deployment.
- `AI_MODEL_API_KEY`: API key for the AI model/agent.
- `GMAIL_REFRESH_TOKEN`: (If applicable) for OAuth2 flow.

### Actions
- Deployment workflows should use the `google-github-actions/auth` for secure authentication.
- Monitor workflow runs via `gh run list`.
