# PEB Service – Todo

## Future Considerations 🤔

- [ ] **Rename Firestore database from `pathway` to `(default)`**
  - Named databases cause IAM permission headaches — `roles/datastore.user` isn't enough,
    you also need `roles/datastore.owner`. The `(default)` database just works with `roles/datastore.user`.
  - Would require updating: `service/main.py`, all integration tests
  - Risk: data migration needed (or recreate in new DB)
- [ ] **Browser-based sign-in test** (playwright) — automate login flow verification
- [ ] **Portal UX redesign for scenario buttons**
  - "Start" button → "Practice Scenario" 
  - If active scenario: show "Active" (greyed out) instead of start button
  - For REPLY scenarios when active: show "Resend Email" button
  - Research: will Gmail mark bot replies as spam? (probably not if users are actively replying)
- [x] **Student name personalization in starter emails** *(done)*
  - All 8 reply scenarios use `{student_name}` placeholder
  - Firestore rules validate firstName (no `<>`, 1-100 chars) + restrict fields
  - Portal collects name on first login, editable in header
  - Remaining: deploy Firestore rules + Cloud Function