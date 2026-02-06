# Student Portal & PEB Service Integration TODO

## 🎯 Vision

Enable students to practice professional email skills by:
1. Selecting scenarios from the student portal
2. Receiving scenario instructions via email
3. Replying with their response
4. Getting AI-graded feedback
5. Viewing scores and past attempts in the portal

---

## 📊 Proposed Data Model (Firestore)

### Option A: User-Centric (Recommended for Portal)
```
users/{userId}/
  ├── email: string
  ├── createdAt: timestamp
  └── scenarios: {
        "scenario-1": {
          status: "not-started" | "pending" | "graded",
          attempts: [
            {
              attemptId: string,
              submittedAt: timestamp,
              score: number,
              feedback: string,
              submission: string,
              gradedAt: timestamp
            }
          ]
        }
      }
```

**Pros**: 
- Single read to get all user data
- Efficient for student portal dashboard
- Natural access pattern (users view their own data)

**Cons**: 
- Document size limit (1MB) - unlikely to hit with text
- Harder to query across all users for analytics

### Option B: Scenario-Centric (Alternative)
```
scenarios/{scenarioId}/
  └── attempts/{attemptId}/
        ├── userId: string
        ├── email: string
        ├── submittedAt: timestamp
        ├── score: number
        ├── feedback: string
        └── submission: string
```

**Pros**: 
- Easy to query all attempts for a scenario
- Better for instructor analytics

**Cons**: 
- Multiple reads to build user dashboard
- Requires composite index for user queries

### Recommendation
Use **Option A** with Firestore Security Rules to ensure users only access their own data.

---

## 🔄 Proposed User Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Student Portal │     │    Firestore    │     │   PEB Service   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │ 1. Click "Start"      │                       │
         ├──────────────────────►│                       │
         │   Create attempt doc  │                       │
         │   status: "pending"   │                       │
         │                       │                       │
         │ 2. Call Cloud Fn      │                       │
         │───────────────────────┼──────────────────────►│
         │   (scenarioId, email) │                       │
         │                       │                       │
         │                       │    3. Send scenario   │
         │                       │       email with      │
         │                       │    custom FROM name   │
         │                       │◄──────────────────────┤
         │                       │                       │
         │                       │    4. Student replies │
         │                       │       to email        │
         │                       │───────────────────────►
         │                       │                       │
         │                       │    5. Grade response  │
         │                       │       & update        │
         │                       │       Firestore       │
         │                       │◄──────────────────────┤
         │                       │   status: "graded"    │
         │                       │                       │
         │ 6. Real-time listener │                       │
         │    shows graded       │                       │
         │◄──────────────────────┤                       │
         │                       │                       │
```

---

## 📧 Email FROM Name Customization

**Answer: YES, email systems support custom display names!**

Gmail allows setting a display name separate from the email address:
```
From: "Bob Jones (Manager Bot)" <pathwayemailbot@gmail.com>
```

In Gmail API, set the `From` header in the raw message. Each scenario JSON can include:
```json
{
  "scenario_id": "1",
  "from_name": "Bob Jones (Manager)",
  "instructions": "..."
}
```

---

## ❓ Open Questions

### 1. How does student portal trigger the scenario email?
- **Option A**: HTTP Cloud Function endpoint (simple, direct)
- **Option B**: Write to Firestore → Cloud Function trigger (decoupled)
- **Option C**: Pub/Sub message (existing pattern in pebservice)

**Recommendation**: Option A for simplicity. Create `sendScenarioEmail` Cloud Function.

### 2. How does pebservice know which user/scenario to associate the reply with?
- **Option A**: Email address match only (current approach)
- **Option B**: Include scenario ID in subject line (e.g., "Re: [Scenario-1] Introduction")
- **Option C**: Store "active scenarios" per email in Firestore, match by email + timestamp

**Recommendation**: Option B - modify subject line to include scenario ID for reliable matching.

### 3. Real-time updates or polling?
- **Option A**: Firestore real-time listeners (best UX, instant feedback)
- **Option B**: Manual refresh/polling (simpler, less overhead)

**Recommendation**: Option A - Firestore listeners are built-in and provide great UX.

### 4. How to handle multiple concurrent scenarios?
- Can a student start multiple scenarios at once?
- Should we limit to one active scenario at a time?

**Recommendation**: Allow multiple, but track each attempt separately with attemptId.

### 5. Where should scenario JSON files live?
- **Option A**: Keep in pebservice repo, read from filesystem
- **Option B**: Store in Firestore for easier access
- **Option C**: Store in Cloud Storage bucket

**Recommendation**: Start with Option A (current), migrate to Option B for easier portal access.

---

## 🎯 Implementation Plan

### Phase 1: Data Foundation
1. **Define Firestore schema** (use Option A above)
2. **Create Firestore Security Rules** (users can only read/write their own data)
3. **Set up Firestore emulator** for local testing
4. **Create seed data** for testing

### Phase 2: Update PEB Service
1. **Add FROM name to scenario JSON files**
2. **Update email sending** to use custom FROM name from scenario
3. **Add Firestore write** after grading (store score, feedback, submission)
4. **Update scenario matching** to use subject line with scenario ID
5. **Make scenario selection dynamic** (read from JSON files, not hardcoded)

### Phase 3: Create Cloud Function Trigger
1. **Create `sendScenarioEmail` HTTP Cloud Function**
   - Input: `{ userId, scenarioId, email }`
   - Action: Read scenario JSON, send email with instructions
   - Update Firestore: set status to "pending"
2. **Deploy and test** with local student portal

### Phase 4: Update Student Portal
1. **Connect to Firestore** (read user's scenario data)
2. **Update scenario cards** to show real status (not-started, pending, graded)
3. **Implement "Start" button** → call Cloud Function
4. **Add real-time listener** for status updates
5. **Create score detail view** (show submission + feedback)
6. **Add "previous attempts" list** for scenarios with multiple scores

### Phase 5: Polish & Deploy
1. **Add loading states** and error handling
2. **Test end-to-end flow** with real emails
3. **Deploy student portal** to GitHub Pages
4. **Update documentation** with new flow
5. **Create instructor view** (optional: see all student progress)

---

## 🤔 Additional Considerations

### Security
- **Firestore Security Rules**: Ensure students can only access their own data
- **Cloud Function auth**: Verify user is authenticated before sending scenario email
- **Rate limiting**: Prevent spam/abuse (limit scenarios per day?)
- **Email validation**: Ensure only authorized domains can use the portal

### User Experience
- **Email deliverability**: Continue monitoring spam folder issue
- **Mobile responsiveness**: Ensure portal works on phones/tablets
- **Accessibility**: Screen reader support, keyboard navigation
- **Error messages**: Clear, actionable feedback for students

### Scalability
- **Firestore costs**: Monitor read/write operations as user base grows
- **Cloud Function cold starts**: Consider min instances for better UX
- **Email quota**: Gmail API has daily limits (check current usage)
- **Concurrent scenarios**: Test with multiple students doing same scenario

### Data & Analytics
- **Aggregate statistics**: Average scores per scenario, completion rates
- **Instructor dashboard**: View class progress, identify struggling students
- **Export data**: Allow students to download their submissions/feedback
- **Retention policy**: How long to keep old attempts?

### Testing
- **Unit tests**: For grading logic, Firestore writes
- **Integration tests**: End-to-end flow with test emails
- **Load testing**: Simulate multiple concurrent users
- **Firestore emulator**: Test locally without hitting production

### Documentation
- **Student onboarding**: How to use the portal, what to expect
- **Instructor guide**: How to add scenarios, view progress
- **Developer docs**: Architecture, deployment, troubleshooting
- **API documentation**: Cloud Function endpoints, Firestore schema

### Future Enhancements
- **Scenario authoring UI**: Let instructors create scenarios without editing JSON
- **Peer review**: Students review each other's emails
- **Leaderboard**: Gamification (optional, consider privacy)
- **Email templates**: Provide starter templates for common scenarios
- **Multi-language support**: Spanish, Portuguese, etc.
- **Integration with LMS**: Canvas, Blackboard, etc.

---

## 📝 Next Session Goals

1. Finalize Firestore schema (review Option A)
2. Create Firestore Security Rules
3. Update one scenario JSON with FROM name
4. Test custom FROM name in email
5. Create `sendScenarioEmail` Cloud Function (basic version)

---

## 🔗 Related Files

- `pebservice/scenarios/*.json` - Scenario definitions
- `pebservice/src/index.ts` - Email handling and grading
- `student-portal/src/pages/scenarios.ts` - Scenario list UI
- `student-portal/src/firebase-config.ts` - Firebase initialization