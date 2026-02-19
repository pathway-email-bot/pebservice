# Architecture & Design Decisions

## Technology Choices

### Why GitHub Pages for the Portal?
- Free hosting with automatic HTTPS
- Simple deployment via GitHub Actions
- No server management — static site talks directly to Firebase + Cloud Functions

### Why Same GCP Project for Everything?
- Unified IAM (Cloud Functions access Firestore without cross-project bindings)
- Single billing account
- Simpler security configuration

### Why TypeScript for the Portal?
- Better autocomplete for Firebase SDK
- Type safety for Firestore data models
- AI assistance works better with types
- Vite strips types at dev time via esbuild — **zero** dev-server overhead vs vanilla JS

### Why Monorepo?
Originally two repos (`pebservice` + `student-portal`). Merged into one monorepo (Feb 2026) for simpler cross-component work. GitHub Actions path filters keep deployments independent.

---

## Firebase Setup (Reproducibility)

These are the CLI commands used to set up Firebase on the GCP project.

### Prerequisites
- gcloud CLI authenticated
- Node.js installed

### Commands Executed

```powershell
# 1. Enable Firebase APIs on the GCP project
gcloud services enable firebase.googleapis.com firestore.googleapis.com identitytoolkit.googleapis.com --project=pathway-email-bot-6543

# 2. Add Firebase resources to the GCP project
npx firebase-tools projects:addfirebase pathway-email-bot-6543

# 3. Create a Web App
npx firebase-tools apps:create WEB student-portal --project=pathway-email-bot-6543
# Output: App ID: 1:687061619628:web:6d94d1f35ca45176c16009

# 4. Get SDK config
npx firebase-tools apps:sdkconfig WEB 1:687061619628:web:6d94d1f35ca45176c16009 --project=pathway-email-bot-6543
```

### Remaining Manual Steps (Firebase Console)

1. **Enable Email/Password Auth** — Authentication → Sign-in method
2. **Enable Magic Links** — Same page, toggle "Email link (passwordless sign-in)"
3. **Create Firestore Database** — Firestore → Create database (production mode, us-central)

### Useful Commands

```powershell
# List Firebase projects
npx firebase-tools projects:list

# List apps in project
npx firebase-tools apps:list --project=pathway-email-bot-6543
```
