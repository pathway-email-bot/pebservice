# Student Portal - Firebase Setup Commands

This documents the CLI commands used to set up Firebase, for reproducibility.

## Prerequisites
- gcloud CLI authenticated
- Node.js installed

## Commands Executed

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

## Remaining Manual Steps

1. **Enable Email/Password Auth** - Firebase Console > Authentication > Sign-in method
2. **Enable Magic Links** - Same page, toggle "Email link (passwordless sign-in)"
3. **Create Firestore Database** - Firebase Console > Firestore > Create database

## Useful Commands

```powershell
# List Firebase projects
npx firebase-tools projects:list

# List apps in project
npx firebase-tools apps:list --project=pathway-email-bot-6543

# Check Firebase status
.\scripts\check_firebase.ps1
```
