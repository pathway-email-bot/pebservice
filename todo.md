# PEB Service – Todo

## Completed ✅

- [x] Fix OAuth token JSON parsing in `main.py`
- [x] Simplify Firestore `get_active_scenario()` — read from user doc
- [x] Fix case-insensitive email header lookup (`get_header()` helper)
- [x] Fix scenario loader path resolution (resolve relative to `scenarios/` dir)
- [x] Fix `Scenario` model — add `interaction_type` field
- [x] Set memory to 512Mi (was OOM at default 256Mi)
- [x] Add verbose logging throughout `main.py`
- [x] Install `google-cloud-secret-manager` in local venv
- [x] Local pipeline test — all 7 steps pass
- [x] **Full E2E test passes** — attempt graded: score=18, status=graded
- [x] Add `@log_function` decorator: log start/end time, params, return value, errors
- [x] Move `auth_utils.py` from `service/` to `scripts/` (local dev utility only)
- [x] Unit tests — 137 passing across 11 test files mirroring `service/` structure
- [x] Coverage enforcement meta-test (auto-fails if new service files lack tests)
- [x] Integration tests: Secret Manager access (6 tests) — passing
- [x] Integration tests: Firestore CRUD (3 tests) — passing
- [x] Deploy pipeline updated: unit tests pre-deploy, integration tests post-deploy
- [x] Created `peb-test-runner` SA for integration tests (2026-02-14)
- [x] Created `tests/conftest.py` for auto credential discovery
- [x] Separated test deps into `tests/requirements.txt`
- [x] Added `pytest-timeout` to `tests/requirements.txt`
- [x] Documented full SA inventory and IAM in `service_notes.md`
- [x] **Lazy watch renewal** — auto-renews Gmail push notifications from `start_scenario` using Firestore transaction + in-memory cache (distributed-safe)

## Active – Priority Order 🔜

### P0 — Site is broken for users (~30 min)
- [ ] **Fix portal login redirect** 🔴
  - Login redirect goes to `https://pathway-email-bot.github.io/pebservice/scenarios?...`
  - Returns 404 — the page doesn't exist at that path
  - Likely a Vite `base` config or Firebase Auth `actionCodeSettings.url` mismatch
  - Need to check: `portal/vite.config.ts`, `portal/src/auth.ts`, Firebase console authorized domains

### P1 — CI pipeline needs new GitHub secret (~5 min)
- [ ] **Update `GCP_DEPLOYER_KEY` GitHub secret**
  - Add contents of `deployer-key.secret.json` as GitHub secret `GCP_DEPLOYER_KEY`
  - Can remove old `GCP_SA_KEY` secret after verifying

### P2 — Validate E2E grading flow (~10 min)
- [ ] **Run full E2E integration test locally** (`test_e2e_grading.py`)
  - Sends real email → polls Firestore for grading → asserts score/feedback
  - Needs `client_config.secret.json` + `token.test.secret.json` present
  - Cost: ~$0.01 per run (OpenAI API call)

### P3 — Verify full pipeline end-to-end (~20 min)
- [ ] **Push and verify pipeline runs**
  - Push triggers deploy + both test stages
  - CI needs `gmail-refresh-token-test` accessible for E2E test
  - Validate: unit tests → deploy → integration tests (all green)

### P4 — Gmail tokens need refresh (~10 min)
- [x] **Refresh bot Gmail token** — uploaded v4 to Secret Manager (2026-02-14)
- [x] **Refresh test Gmail token** — uploaded v3 to Secret Manager (2026-02-14)

### P5 — Housekeeping
- [x] **Clean up dead scripts** — deleted 16 unused scripts, updated docs (2026-02-14)

## Future Considerations 🤔

- [ ] **Rename Firestore database from `pathway` to `(default)`**
  - Named databases cause IAM permission headaches — `roles/datastore.user` isn't enough,
    you also need `roles/datastore.owner`. The `(default)` database just works with `roles/datastore.user`.
  - Would require updating: `service/main.py`, all integration tests
  - Risk: data migration needed (or recreate in new DB)
- [x] ~~**Tighten runtime SA permissions**~~ — created `peb-runtime` with least-privilege roles (2026-02-14)
- [x] ~~**Remove unused App Engine SA editor role**~~ — removed `roles/editor` (2026-02-14)
- [x] ~~**Rename SAs for clarity**~~ — `peb-deployer` (was `peb-service-account`), `peb-runtime` (was default compute SA) (2026-02-14)
- [ ] **Browser-based sign-in test** (playwright) — automate login flow verification
- [ ] **Portal UX redesign for scenario buttons**
  - "Start" button → "Practice Scenario" 
  - If active scenario: show "Active" (greyed out) instead of start button
  - For REPLY scenarios when active: show "Resend Email" button
  - Research: will Gmail mark bot replies as spam? (probably not if users are actively replying)
- [x] **Rename `send_scenario_email` → `start_scenario`** — consolidated attempt creation server-side (2026-02-14)