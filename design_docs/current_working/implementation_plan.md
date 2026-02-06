# End-to-End Student Portal Flow

Enable students to: log in → select a scenario → receive scenario email → respond → get AI feedback/score → view results.

## ✅ Completed: Planning & Infrastructure

**Monorepo Setup** (2026-02-06):
- ✅ Merged `student-portal` into `pebservice/portal/`
- ✅ Renamed `src/` → `service/`
- ✅ Created separate GitHub Actions workflows for service and portal
- ✅ Deployed portal to GitHub Pages: https://pathway-email-bot.github.io/pebservice/
- ✅ Made repo public (free GitHub Pages)

**All Open Issues Resolved**:
- ✅ Issue 1: Firebase ID token authentication
- ✅ Issue 2: Build-time scenario bundling
- ✅ Issue 3: Firestore security rules defined
- ✅ Issue 4: Deployment URL confirmed
- ✅ Issue 5: Local testing strategy defined

**Ready for Implementation**: All infrastructure decisions made, ready to build the end-to-end flow.

---

## Current State

| Component | Status |
|-----------|--------|
| Monorepo structure | ✅ Complete |
| Portal deployment | ✅ Live at GitHub Pages |
| Firebase Auth (magic link) | ✅ Working |
| Scenarios page UI | ⚠️ Hardcoded 6 scenarios |
| pebservice email processing | ✅ Working (hardcoded scenario) |
| 11 scenario JSONs | ✅ Exist in `service/email_agent/scenarios/` |
| Firestore integration | ❌ Not connected |
| Scenario triggering from portal | ❌ Not implemented |

---

## Next: Implementation Tasks

## Proposed Changes

### Student Portal (`portal`)

#### [NEW] `src/scenarios-api.ts`
- **Load scenarios from build-time bundled static files** (fetched during GitHub Actions build)
  - JSONs copied from `service/email_agent/scenarios/` → `portal/public/scenarios/` at build time
  - Single source of truth: scenarios only in service side
  - New scenarios require redeploying portal (handled by monorepo triggers)
- Call Cloud Function to start a scenario
- Types for scenario metadata

#### [MODIFY] `src/pages/scenarios.ts`
- Replace hardcoded scenarios with runtime fetch from `listScenarios()`
- **Single active scenario UX**:
  - Scenario cards show title + brief description only (instructions hidden)
  - Clicking "Start" reveals full instructions + marks scenario as active
  - Only one scenario can be "open" at a time (drawer metaphor)
  - Active scenario is visually distinct: highlighted border, "ACTIVE" badge, or subtle glow
  - Clicking "Start" on a new scenario abandons the previous one (with confirmation if pending)
- Add Firestore real-time listener for attempt status updates
- Show score/feedback inline when graded

#### [NEW] `src/firestore-service.ts`
- CRUD for user attempts in Firestore
- Real-time listeners for status updates
- Types matching Firestore schema

---

### PEB Service (`pebservice`)

#### [NEW] `src/send_scenario.py` - HTTP Cloud Function

**Endpoint**: `POST /sendScenarioEmail`

**Request body**:
```json
{
  "email": "student@example.com",
  "scenarioId": "missed_remote_standup"
}
```

**What it does**:
1. Load scenario JSON from `src/email_agent/scenarios/{scenarioId}.json`
2. Generate starter email using `EmailAgent.build_starter_thread()` (already exists in email_agent)
3. Send email via Gmail API with:
   - **FROM**: `"Jordan Smith (Engineering Manager)" <pathwayemailbot@gmail.com>` (from `starter_sender_name`)
   - **SUBJECT**: `[PEB:missed_remote_standup] Missed standup this morning` (tagged for tracking)
   - **BODY**: Generated or from `starter_email_body`
4. Create Firestore doc at `users/{email}/attempts/{attemptId}` with status "pending"
5. Return `{ attemptId, success: true }`

**Response**:
```json
{
  "success": true,
  "attemptId": "abc123",
  "message": "Scenario email sent"
}
```

---

> **Note**: `listScenarios` endpoint NOT needed - scenarios are bundled into portal at build time.

---

#### [MODIFY] `src/main.py` - Existing Pub/Sub Function

**Design Decision: How does pebservice know which scenario an email belongs to?**

##### Scenario Types

| Type | Example | Who sends first? |
|------|---------|------------------|
| **Reply** | "You missed standup, explain yourself" | Bot sends prompt, student replies |
| **Initiate** | "Write an email to request time off" | Student sends from scratch |

---

##### Option A: Subject Line Token `[PEB:xyz]`
- Bot includes `[PEB:missed_remote_standup]` in subject
- Student reply preserves it via "Re: [PEB:...]"
- ❌ Doesn't work for student-initiates scenarios
- ❌ Visible/ugly in subject line

##### Option B: Hidden Body Token
- Bot email contains `<!-- PEB:missed_remote_standup -->` or similar
- Parse from thread when reply comes in
- ❌ Doesn't work for student-initiates scenarios
- ⚠️ Email clients may strip HTML comments

##### Option C: Thread History Lookup
- When email arrives, check if thread contains a prior bot-sent email
- Look up original scenario from that email's metadata
- ❌ Doesn't work for student-initiates scenarios
- ❌ Extra API calls per message

##### Option D: Firestore as Source of Truth ✅ (Recommended)

**Flow for REPLY scenarios:**
1. Portal calls `sendScenarioEmail` → creates Firestore doc with `{ email, scenarioId, status: "pending" }`
2. Bot sends email (no special tokens needed)
3. Student replies
4. pebservice receives email → queries Firestore: "What pending scenario does this email have?"
5. Loads that scenario, grades, updates Firestore

**Flow for STUDENT-INITIATES scenarios:**
1. Portal shows scenario instructions on screen (e.g., "Write an email requesting time off")
2. Portal calls `startScenario` → creates Firestore doc with `{ email, scenarioId, status: "awaiting_student_email" }`
3. Student composes fresh email to `pathwayemailbot@gmail.com`
4. pebservice receives email → queries Firestore: "What active scenario does this email have?"
5. Grades the cold email, sends feedback reply

**Firestore query in main.py:**
```python
def get_active_scenario(email: str) -> tuple[str, str] | None:
    """Returns (scenario_id, attempt_id) or None if no active scenario"""
    attempts = db.collection('users').document(email) \
        .collection('attempts') \
        .where('status', 'in', ['pending', 'awaiting_student_email']) \
        .order_by('startedAt', direction='DESCENDING') \
        .limit(1) \
        .get()
    
    if attempts:
        doc = attempts[0]
        return (doc.get('scenarioId'), doc.id)
    return None
```

**Benefits:**
- ✅ Works for both reply and initiate scenarios
- ✅ No ugly tokens in emails
- ✅ Single source of truth
- ✅ Portal always knows scenario state

**Error handling for unknown emails:**
```python
if not active_scenario:
    # Log for investigation
    logger.warning(f"Email from {sender} with no active scenario")
    logger.info(f"Subject: {subject}")
    logger.info(f"Body preview: {body[:500]}")
    
    # Send redirect response
    send_reply(service, msg, 
        "Thanks for your email! To practice email scenarios, please visit the student portal "
        "and click 'Start' on a scenario first. Then reply to the scenario email you receive.\n\n"
        "Portal: https://pathway-email-bot.github.io/pebservice/")
    return
```

> **Future consideration**: Could use AI to infer intended scenario, but for now just log and redirect to see if this is a common issue.

---

#### [NEW] `src/firestore_client.py`

```python
from google.cloud import firestore

def get_firestore_client():
    """Returns Firestore client (uses default credentials in Cloud Functions)"""
    return firestore.Client()

def create_attempt(email: str, scenario_id: str) -> str:
    """Create new attempt, returns attemptId"""
    ...

def update_attempt_graded(email: str, attempt_id: str, score: int, max_score: int, feedback: str):
    """Mark attempt as graded with results"""
    ...
```

---

## Firestore Schema

```
users/{email}/
  ├── activeScenarioId: string | null      # Only ONE scenario active at a time
  ├── activeAttemptId: string | null
  └── attempts/{attemptId}/
        ├── scenarioId: string
        ├── status: "active" | "graded" | "abandoned"
        ├── startedAt: timestamp
        ├── score: number (after grading)
        ├── maxScore: number
        ├── feedback: string
        ├── gradedAt: timestamp
```

> **Key decision**: `activeScenarioId` is a single field, not a query. Only one scenario can be active per user.

---

## Minimum Viable Flow (Today's Goal)

```
1. Student logs in (existing)
2. Portal loads scenario list from bundled static files (fetched at build time)
3. Student sees scenario list
4. Student clicks "Start" → calls Cloud Function sendScenarioEmail
5. Cloud Function sends scenario email + creates Firestore doc
6. Student replies to email
7. pebservice grades reply → updates Firestore
8. Portal shows score via real-time listener
```

**Deployment flow for new scenarios:**
- Add new scenario JSON to `service/email_agent/scenarios/`
- Commit and push to main branch
- GitHub Actions auto-triggers portal deployment (via path filter)
- Portal build copies JSON, bundles it, and deploys to GitHub Pages
- Students see new scenario immediately

---

## Verification Plan

### Manual End-to-End Test
1. Run student portal locally: `npm run dev`
2. Log in with a test email
3. Click "Start" on a scenario
4. Check email inbox for scenario prompt
5. Reply to the email with a test response
6. Wait for pebservice to process (check Cloud Function logs)
7. Verify score appears in portal

### Cloud Function Logs
```bash
gcloud functions logs read process-email --project=pathway-email-bot-6543 --limit=20
```

---

## Open Issues (Resolve Before Implementation)

### Issue 1: Portal → Cloud Function Authentication

**Question**: How does the portal authenticate requests to `sendScenarioEmail` and `listScenarios`?

**Decision**: ✅ **Firebase ID Token (Option B)**

Firebase magic link sign-in provides an ID token that:
- Proves the user authenticated with that email
- Can be sent in `Authorization: Bearer <token>` header
- Cloud Function validates via Firebase Admin SDK

```typescript
// Portal side
const token = await auth.currentUser?.getIdToken();
fetch(cloudFunctionUrl, {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

```python
# Cloud Function side
from firebase_admin import auth
decoded = auth.verify_id_token(token)
email = decoded['email']
```

**CORS**: Keep config in code. Finalize allowed origins after deployment URL is confirmed (likely GitHub Pages).

---

### Issue 2: Scenario List Source

**Question**: Where does the portal get the list of available scenarios?

**Decision**: ✅ **Build-time fetch with monorepo triggers**

GitHub Actions workflow fetches scenarios during portal deployment and bundles them as static files:

```yaml
# .github/workflows/deploy-portal.yml
name: Deploy Portal

on:
  push:
    paths:
      - 'portal/**'
      - 'service/email_agent/scenarios/**'  # Redeploy portal when scenarios change
      - '.github/workflows/deploy-portal.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Fetch scenarios from service
        run: |
          mkdir -p portal/public/scenarios
          cp service/email_agent/scenarios/*.json portal/public/scenarios/
      
      - name: Build portal
        run: cd portal && npm install && npm run build
      
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./portal/dist
```

Portal reads static files:
```typescript
// src/scenarios-api.ts
async function listScenarios(): Promise<ScenarioMetadata[]> {
  const response = await fetch('/pebservice/scenarios/'); // Static files from build
  const dir = await response.json(); // Or manually list if no directory listing
  const scenarios = await Promise.all(
    dir.map(filename => fetch(`/pebservice/scenarios/${filename}`).then(r => r.json()))
  );
  return scenarios;
}
```

**Benefits**:
- ✅ Single source of truth: scenario JSONs only in `service/email_agent/scenarios/`
- ✅ No duplication
- ✅ No runtime API dependencies or rate limits
- ✅ Fast: static file reads
- ✅ Monorepo triggers: updating a scenario JSON auto-redeploys both services
- ✅ Clean coupling: only JSON files and location

---

### Issue 3: Firestore Security Rules

**Decision**: ✅ **Users can read/write only their own docs**

The same Firebase ID token works for both Cloud Functions AND Firestore:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{email} {
      allow read, write: if request.auth != null 
                         && request.auth.token.email == email;
    }
    match /users/{email}/attempts/{attemptId} {
      allow read, write: if request.auth != null 
                         && request.auth.token.email == email;
    }
  }
}
```

**What this enables**:
- Portal reads user's grades directly from Firestore (no API needed)
- Portal can update user's activeScenarioId when starting
- Cloud Functions (Admin SDK) bypass rules for grading writes

---

### Issue 4: Portal Deployment URL

**Decision**: ✅ **GitHub Pages (Option A)**

After monorepo migration:
- **URL**: `https://pathway-email-bot.github.io/pebservice/`
- **Deployment**: Via `.github/workflows/deploy-portal.yaml`
- **CORS allowed origin**: `https://pathway-email-bot.github.io`

---

### Issue 5: Local Testing Strategy

**Decision**: ✅ **Firestore emulator + manual email testing**

**Local development workflow**:
1. `cd portal && npm run dev` - Run portal locally
2. `firebase emulators:start --only firestore` - Run Firestore emulator
3. Portal connects to emulator for testing UI/data flow
4. Email flow requires deployed pebservice (test manually)

**Note**: Full end-to-end testing requires deployment since email sending/receiving can't be emulated.
