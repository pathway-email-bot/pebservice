# PEB Service – Todo

## Future Considerations 🤔

- [ ] **Browser-based sign-in test** (playwright) — automate login flow verification
- [ ] **Investigate how we can not be marked as spam**
- [ ] **Share with Tom Kerby**
- [ ] **Audit API quotas for `pathwayemailbot@gmail.com` and test email** — we're using a single Gmail address like a web service; review quotas/rate limits for every API we call (Gmail send, Gmail watch, Gmail history, Firebase Auth, Firestore, OpenAI, Secret Manager) and document in a table

## UX Fixes

- [x] **Scenario drawer: show all relevant data in header** — include link to previous attempts and their feedback
- [x] **Show grading results on initial page load** — data that currently only appears via Firestore real-time updates should also be present when the page first loads
- [x] **Allow exploring scenarios without starting them** — users should be able to browse/read a scenario without triggering an active attempt, and navigate between scenarios freely
- [ ] **End-to-end email testing** — verify emails are actually being sent and received
- [x] **Auto-expire stale active attempts** — on page load, only show a scenario as "active" if the attempt is recent; treat old unfinished attempts as abandoned (timestamp already exists on attempts)
- [x] **Clearly communicate interaction type (initiate vs reply)** — users can get confused when an email doesn't show up because they're actually supposed to send one. The UX needs to clearly signal whether the user initiates the email or replies to one — e.g. labeling scenarios with "(You initiate)" / "(You reply)", or making the action button itself communicate this. Think through the whole flow from the user's perspective to find the most intuitive approach.
- [x] **Decouple drawer expansion, active attempt, and scenario start** — currently these three actions are overloaded: expanding a scenario drawer also starts it and sets the active attempt. Should a user be able to explore/read scenarios without starting them? Should browsing a different scenario swap the active attempt? Consider a UX paradigm that cleanly separates exploration from commitment.

## Browser E2E Test 🧪

Single happy-path flow using `michaeltreynolds.test@gmail.com`:

1. **Login** — navigate to portal, enter test email, submit magic link form
2. **Get magic link** — use Gmail API (test account token via Secret Manager) to read the sign-in email from inbox, extract the magic link URL
3. **Navigate to magic link** — open the link in the browser, verify redirect to scenarios page
4. **Enter name** — name modal appears, type first name, submit
5. **Start an initiate scenario** — click a scenario card to expand drawer, click "Start — You Send First"
6. **Send email** — use Gmail API (test account token) to send a test email to `pathwayemailbot@gmail.com` with the correct subject line
7. **Wait for score** — poll the page (or Firestore) until grading results appear in the UX (score badge + feedback)
8. **Done!** — assert score is present and feedback is non-empty

## Grading & Rubrics

- [ ] **Review rubric communication** — the grading feels too tough, and it's unclear whether the rubric is being communicated well to students before/during attempts. Are students aware of what they're being evaluated on?
- [ ] **Audit rubric evaluation quality** — assess whether the AI is evaluating rubric criteria fairly and accurately. Are the rubrics themselves correct and reasonable for each scenario?
- [ ] **Golden file regression tests** — save sample student emails, run through grading pipeline, assert score/feedback are reasonable. Catches prompt regressions.

## Scenario Quality

- [ ] **Review each scenario for student success** — scenarios are currently theoretical and may set students up to fail. Go through each scenario and identify gaps, e.g. a scenario references "a report you sent" but the student never actually sent one and has no context. Consider generating simple supporting artifacts (e.g. a 3-line report) in the scenario instructions so students have concrete material to work with.
