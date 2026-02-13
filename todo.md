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
- [x] Integration tests: Secret Manager access (6 tests) — ✅ passing
- [x] Integration tests: Firestore CRUD (3 tests) — ✅ passing
- [x] Deploy pipeline updated: unit tests pre-deploy, integration tests post-deploy

## Next Up 🔜

- [ ] **Run full E2E integration test locally** (`test_e2e_grading.py`)
  - Sends real email → polls Firestore for grading → asserts score/feedback
  - Needs `client_config.secret.json` + `token.test.secret.json` present
  - Cost: ~$0.01 per run
- [ ] **Verify pipeline runs** — push triggers deploy + both test stages
  - CI needs `gmail-test-token` secret stored for E2E (currently only local)
  - May need to add `gmail-refresh-token-test` to the SA's Secret Manager access
- [ ] Schema consistency audit between scripts, tests, and service code
- [ ] Consider adding `pytest-timeout` to `requirements.txt` for E2E tests
