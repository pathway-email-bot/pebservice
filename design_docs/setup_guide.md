# Student Portal - Setup Guide

## 📋 Project Overview

**Purpose**: A web-based student portal for practicing email communication skills through interactive scenarios.

**Architecture**:
- **Frontend**: Static site (Vite + TypeScript) hosted on GitHub Pages
- **Backend**: Google Cloud Project (`pebservice` / `pathway-email-bot`)
- **Database**: Firebase Firestore (student progress, scores)
- **Auth**: Firebase Authentication (Magic Links / Email Sign-in)

---

## 🏗️ Technology Stack

### Frontend
- **Build Tool**: Vite 7.x
- **Language**: TypeScript (pragmatic, simple interfaces)
- **Styling**: Vanilla CSS
- **Hosting**: GitHub Pages

### Backend (Shared with PEB Service)
- **Cloud Provider**: Google Cloud Platform
- **Project**: `pathway-email-bot` (existing)
- **Database**: Cloud Firestore
- **Authentication**: Firebase Auth
- **Email Service**: Cloud Functions + Gmail API (existing)

---

## 🚀 Local Development Setup

### Prerequisites
- Node.js (v18+)
- npm (v9+)
- Git
- Google Cloud account with `pathway-email-bot` project

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd student-portal
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure Firebase** (See Firebase Setup section below)

4. **Run development server**
   ```bash
   npm run dev
   ```
   Visit `http://localhost:5173/`

5. **Build for production**
   ```bash
   npm run build
   ```
   Output: `dist/` folder

---

## 🔥 Firebase Setup

### Step 1: Enable Firebase on GCP Project

```bash
# Authenticate with Google Cloud
gcloud auth login

# Set the project
gcloud config set project pathway-email-bot

# Enable Firebase (if not already enabled)
# This can also be done via Firebase Console: https://console.firebase.google.com/
```

### Step 2: Create Web App in Firebase Console

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select `pathway-email-bot` project
3. Click "Add app" → Web (</> icon)
4. Register app with nickname: `student-portal`
5. Copy the Firebase config object

### Step 3: Add Firebase Config to Project

Create `src/firebase-config.ts` with the config from Step 2:

```typescript
import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: "...",
  authDomain: "...",
  projectId: "pathway-email-bot",
  storageBucket: "...",
  messagingSenderId: "...",
  appId: "..."
};

// Initialize Firebase
export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
```

### Step 4: Enable Authentication Methods

1. In Firebase Console → Authentication → Sign-in method
2. Enable "Email/Password" provider
3. Enable "Email link (passwordless sign-in)"

### Step 5: Configure Firestore Database

1. In Firebase Console → Firestore Database
2. Create database (Start in **test mode** for development)
3. Choose location (us-central1 recommended)

---

## 📁 Project Structure

```
student-portal/
├── design_docs/           # Documentation & brainstorming
│   ├── idea.md           # Original concept & requirements
│   ├── agent_ideas.md    # Architecture brainstorming
│   ├── setup_guide.md    # This file
│   └── image.png         # UI mockup
├── src/                   # Source code
│   ├── main.ts           # Entry point
│   ├── firebase-config.ts # Firebase initialization
│   ├── style.css         # Global styles
│   └── ...               # Components (to be added)
├── public/               # Static assets
├── index.html           # HTML entry point
├── package.json         # Dependencies
├── tsconfig.json        # TypeScript config
└── vite.config.ts       # Vite config (to be added)
```

---

## 🧪 Testing Locally

### Test Firebase Connection
```typescript
// In browser console after running npm run dev
import { auth, db } from './firebase-config';
console.log('Auth:', auth);
console.log('Firestore:', db);
```

### Test Magic Link Auth
1. Enter email in login form
2. Check email inbox for magic link
3. Click link → Should authenticate user
4. Check `auth.currentUser` in console

---

## 🚢 Deployment (Future)

### GitHub Pages Deployment
- **Branch**: `gh-pages` (auto-created by GitHub Actions)
- **URL**: `https://<username>.github.io/student-portal/`
- **Trigger**: Push to `main` branch

### GitHub Actions Workflow
- Build: `npm run build`
- Deploy: Copy `dist/` to `gh-pages` branch
- (To be configured later)

---

## 🔐 Security Notes

1. **Firebase Config is Public**: The `firebaseConfig` object can be committed to Git. It's designed to be public.
2. **Security Rules**: Firestore security rules protect the data, not the config.
3. **API Keys**: The Firebase API key in the config is restricted to your domain.

---

## 📚 Key Decisions

### Why GitHub Pages?
- Free hosting
- Simple deployment
- No server management
- Automatic HTTPS

### Why Same GCP Project?
- Unified IAM (Cloud Functions can access Firestore easily)
- Single billing account
- Simpler security configuration

### Why Separate Repos?
- Different deployment lifecycles
- Cleaner CI/CD (separate GitHub Actions)
- Better organization (UI vs Backend)

### Why TypeScript?
- Better autocomplete for Firebase SDK
- Type safety for Firestore data models
- AI assistance works better with types
- Minimal overhead with Vite (instant transpilation)

---

## 🆘 Troubleshooting

### Vite dev server won't start
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

### Firebase import errors
```bash
# Ensure Firebase is installed
npm install firebase
```

### TypeScript errors blocking build
```bash
# Check tsconfig.json
# Ensure "strict": false for easier development
```

---

## 📞 Resources

- [Vite Documentation](https://vite.dev/)
- [Firebase Web SDK](https://firebase.google.com/docs/web/setup)
- [Firestore Security Rules](https://firebase.google.com/docs/firestore/security/get-started)
- [GitHub Pages](https://pages.github.com/)
