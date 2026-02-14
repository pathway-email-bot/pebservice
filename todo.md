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

## Active – Priority Order 🔜

### P0 — Site is broken for users (~30 min)
- [ ] **Fix portal login redirect** 🔴
  - Login redirect goes to `https://pathway-email-bot.github.io/pebservice/scenarios?...`
  - Returns 404 — the page doesn't exist at that path
  - Likely a Vite `base` config or Firebase Auth `actionCodeSettings.url` mismatch
  - Need to check: `portal/vite.config.ts`, `portal/src/auth.ts`, Firebase console authorized domains

### P1 — CI pipeline doesn't run integration tests (~15 min)
- [ ] **Update CI workflow for test runner SA**
  - Add `test-runner-key.secret.json` content as GitHub secret `GCP_TEST_SA_KEY`
  - Update `deploy-service.yaml` to use `GCP_TEST_SA_KEY` for the integration test step
  - Separate deploy auth (peb-service-account) from test auth (peb-test-runner)

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

### P4 — Housekeeping (~15 min)
- [ ] Schema consistency audit between scripts, tests, and service code

## Future Considerations 🤔

- [ ] **Rename Firestore database from `pathway` to `(default)`**
  - Named databases cause IAM permission headaches — `roles/datastore.user` isn't enough,
    you also need `roles/datastore.owner`. The `(default)` database just works with `roles/datastore.user`.
  - Would require updating: `service/main.py`, all integration tests, `_local_test.py`
  - Risk: data migration needed (or recreate in new DB)
- [ ] **Tighten runtime SA permissions** — replace `roles/editor` on `687061619628-compute@...`
  with specific roles (`secretmanager.secretAccessor`, `datastore.user`, `pubsub.subscriber`)
- [ ] **Remove unused App Engine SA** — `pathway-email-bot-6543@appspot.gserviceaccount.com`
  has `roles/editor` but isn't used by anything
- [ ] **Browser-based sign-in test** (playwright) — automate login flow verification