# Pathway Email Bot (PEB) - Monorepo

This repository contains both the email grading service and the student portal for practicing professional email skills.

## 📁 Repository Structure

```
pebservice/
├── service/          # Cloud Function for email processing & grading
│   ├── main.py
│   └── email_agent/  # AI grading logic (from tjkerby/email_agent)
├── portal/           # Student-facing web portal
│   ├── src/
│   └── package.json
└── design_docs/      # Planning and documentation
```

## 🚀 Deployments

- **Service**: Deployed to Google Cloud Functions via `.github/workflows/deploy-service.yaml`
- **Portal**: Deployed to GitHub Pages at `https://pathway-email-bot.github.io/pebservice/`

## 🤖 Instructions for Antigravity AI

You are the primary operator and consumer of this repository. Follow these guidelines for management and deployment:

### Tooling & Workflow
- **Repository Management**: Use the **GitHub CLI (`gh`)** for managing issues, pull requests, and repository settings.
- **Secrets Management**: All sensitive information (API keys, service account JSON, etc.) **must** be stored as **GitHub Secrets**. Use `gh secret set` to manage them.
- **Infrastructure Management**: Use the **Google Cloud CLI (`gcloud`)** or the Google Cloud Console for managing GCP resources.
- **Maintenance (CRITICAL)**: **You must update the resource table in `service_notes.md`** whenever a new cloud service or significant resource is added to the project.
- **Deployment**: CI/CD is handled via **GitHub Actions**. Workflows have path filters to deploy only changed components.
- **Accounts**: There is the owner of the cloud account and then there are the emails that are registered with the service and will be monitored. When asking for credentials, make sure to specify which account you are asking for credentials for. michaeltreynolds@gmail.com is the owner and pathwayemailbot@gmail.com is the email that will grant the refresh token for use with the email service.

### Core Architecture
The system follows a serverless, event-driven architecture on Google Cloud:
1. **Trigger**: An email is received in the service's Gmail account.
2. **Notification**: Gmail push notifications trigger a **GCP Pub/Sub** topic.
3. **Processing**: A **Cloud Function** is triggered by the Pub/Sub subscription.
4. **AI Logic**: The function calls an AI model (from [email_agent](https://github.com/tjkerby/email_agent)) to evaluate the email and generate a response.
5. **Response**: The service sends the generated response back to the student via the Gmail API.

## Related Repositories
- **Prototype**: [michaeltreynolds/email_bot](https://github.com/michaeltreynolds/email_bot) (Reference for initial implementation logic of service that only did autoresponding without ai based on specific purple keyword in subject line, this repo will create and maintain a different google cloud project named something like pathaway-email-bot).
- **AI Agent**: [tjkerby/email_agent](https://github.com/tjkerby/email_agent) (Source of rubric and feedback functionality that we'd like connected to an actual email).

## Contributions
If this repository is public, contributions are welcome! Please open an issue or submit a pull request using the `gh` CLI.
