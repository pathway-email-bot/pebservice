# End-to-End Student Portal Flow

Enable students to: log in → select a scenario → receive scenario email → respond → get AI feedback/score → view results.

## Current State

| Component | Status |
|-----------|--------|
| Firebase Auth (magic link) | ✅ Working |
| Scenarios page UI | ⚠️ Hardcoded 6 scenarios |
| pebservice email processing | ✅ Working (hardcoded scenario) |
| 11 scenario JSONs | ✅ Exist in `pebservice/src/email_agent/scenarios/` |
| Firestore integration | ❌ Not connected |
| Scenario triggering from portal | ❌ Not implemented |

---

## Proposed Changes

### Student Portal (`student-portal`)

#### [NEW] `src/scenarios-api.ts`
- Fetch available scenarios from pebservice (or static JSON for now)
- Call Cloud Function to start a scenario
- Types for scenario metadata

#### [MODIFY] `src/pages/scenarios.ts`
- Replace hardcoded scenarios with dynamic fetch from `listScenarios`
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
        "Portal: https://[student-portal-url]")
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
2. Student sees scenario list (fetch from static config for now)
3. Student clicks "Start" → calls Cloud Function
4. Cloud Function sends scenario email + creates Firestore doc
5. Student replies to email
6. pebservice grades reply → updates Firestore
7. Portal shows score via real-time listener
```

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

**Decision**: ✅ **Build-time fetch (Option C)**

GitHub Actions workflow fetches scenarios from pebservice at deploy time:

```yaml
# .github/workflows/deploy.yml
steps:
  - name: Fetch scenarios from pebservice
    run: |
      curl -L https://api.github.com/repos/OWNER/pebservice/contents/src/email_agent/scenarios \
        | jq -r '.[].download_url' \
        | xargs -I {} curl -L {} -o src/scenarios/
      # Or simpler: assume repos side-by-side in CI
```

**Trade-offs accepted**:
- New scenario requires deploying both pebservice AND student-portal
- Aligns with long-term plan to merge into monorepo
- No runtime dependency on external fetch

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

**Question**: Where is the student portal hosted, and what URL goes in error emails?

**Options**:
- **A) GitHub Pages** - Free, simple. URL: `username.github.io/student-portal`
- **B) Firebase Hosting** - Same project as Firestore. URL: `pathway-email-bot-6543.web.app`
- **C) Other** - Vercel, Netlify, etc.

**Considerations**:
- Firebase Hosting keeps everything in one project
- GitHub Pages is already familiar

**Decision**: _TBD_

---

### Issue 5: Local Testing Strategy

**Question**: How do we test the full flow locally before deploying?

**Options**:
- **A) Firestore emulator** - Use `firebase emulators:start`, test portal against local Firestore
- **B) Dev Firestore instance** - Use production Firestore but with test data
- **C) Mocks** - Mock Firestore calls in portal, test UI only

**Considerations**:
- Email sending/receiving can't be fully emulated locally
- Can test portal + Firestore locally, but grading requires deployed pebservice

**Recommended approach**:
1. Use Firestore emulator for portal development
2. Manually test email flow against deployed pebservice

**Decision**: _TBD_
