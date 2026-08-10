# PEB Service – Todo

## Production Safety 🔒

Context: the OpenAI key rotation of 2026-08-10 nearly took the live site down.
The new key is scoped to a BYU-administered OpenAI project whose approved-model
list excludes `gpt-4o`, so writing it to Secret Manager would have caused a 403
on every grading call — **without passing through any CI gate**.

- [ ] **Pin the OpenAI secret version instead of `latest`** — highest value, ~15 min.
      There are two places, and only fixing one does nothing:
      1. `service/secret_utils.py:70` hardcodes `versions/latest` and is the
         *primary* runtime path — the service fetches from the Secret Manager API
         on every grading call. This is why a bad secret version takes effect
         immediately, with no deploy and no restart.
      2. `.github/workflows/deploy-service.yaml:67` binds `--set-secrets=...:latest`,
         but those env vars are only the *fallback* used when Secret Manager is
         unreachable (`secret_utils.py:82`).
      Suggested fix: read the version from an env var (e.g. `OPENAI_KEY_VERSION`,
      default `latest`) set by the workflow, so a rotation requires a deploy and
      therefore runs the test suite.

- [ ] **Audit the three mutation paths into production.** CI only gates one:
      | path | gated? |
      |---|---|
      | code push to `main` | yes — unit → local → deploy → integration |
      | Secret Manager `latest` | **no** — instant and untested |
      | console state (Pub/Sub sub, Firestore indexes, IAM, OAuth consent) | **no** — invisible to the repo |

- [ ] **Schedule risky changes for the gap between cohorts.** ~150 students every
      3 weeks means there is a multi-week window with no active users. Free, and
      more effective than any environment for large refactors.

- [ ] **Check the billing impact of `--min-instances=1`** (`deploy-service.yaml:64`).
      An always-warm instance is the one line most likely to be generating real
      charges against the "zero cost" goal.


## Pre-Production Environment 🧪

Goal: safely clean up the Antigravity-era code without risking the live site.
Recommended shape is a second GCP project (`pathway-email-bot-staging`) with its
own Secret Manager, Firestore, and Pub/Sub.

**The prerequisite is a refactor, not provisioning** — almost nothing is
parameterized today:

- [ ] **Collapse the duplicated backend URL** — the Cloud Run base URL is
      copy-pasted into four files: `portal/src/scenarios-api.ts:9`,
      `warmup.ts:13`, `auth.ts:25`, `feedback.ts:11`. Move to `import.meta.env.VITE_*`
      with a build arg in `deploy-portal.yaml`.
- [ ] **Parameterize the service** — `main.py:77` (bot email), `:78` (CORS origin,
      currently a strict single-origin allowlist that would reject a staging portal),
      `:243` (portal URL), `:466` (magic-link continue URL), `:866` (feedback
      recipient); `gmail_client.py:136` (reply From), `:262` (watch topic);
      `auth.py:18` (Pub/Sub signer SA); `firestore_client.py:20` (database name).
- [ ] **Parameterize the Firebase web config** — `portal/src/firebase-config.ts:7-14`.
- [ ] **Write the missing provisioning scripts.** `readme.md:209` references
      `scripts/sync_secrets.py` and `service_notes.md:181` references
      `setup_infra.ps1`; neither exists. Staging is the reason to write them.
- [ ] **Commit the Firestore composite index.** There is no `firestore.indexes.json`,
      but `portal/src/firestore-service.ts:141-146` queries
      `status == 'pending' + orderBy(startedAt desc)`, which requires a composite
      index that exists only as manually-created console state. Staging will fail
      that query until it is recreated.

**Portal hosting:** GitHub Pages allows one site per repo, so serve the staging
portal from Firebase Hosting in the staging project (free tier, separate origin,
already in the Firebase ecosystem). Known gap: prod serves under `/pebservice/`
(`vite.config.ts:4`) and staging would serve at `/`, so path-specific bugs will
not reproduce.

**Gmail is the hard part.** A watch is per-account with a single history cursor,
so prod and staging cannot share `pathwayemailbot@gmail.com` — they would fight
over `system/watch_status` and `lastHistoryId`. Staging needs its own bot address.
Trap: a fresh OAuth consent screen in *Testing* status expires refresh tokens
after 7 days, and `gmail.modify` is a restricted scope, so verifying a second app
is real friction. Workaround: reuse the **prod** OAuth client id/secret (already
verified) and authorize the staging Gmail account against it with
`scripts/get_token.py`, storing that refresh token in the staging project's
Secret Manager.


## Cleanup 🧹

- [ ] **Stale docs** — `readme.md:118-122` and `:209-210` describe an `App.tsx` and
      `components/` directory that do not exist (the portal is vanilla TS, not React).
- [ ] **Stale comment** — `service/main.py:9` still says `--trigger-topic=gmail-notifications`;
      wrong name, and a pre-Cloud-Run leftover.
- [ ] **Stale test fixture** — `tests/unit/email_agent/test_email_agent.py:53` mocks
      `model_name: "gpt-4o"`. Harmless (not asserted on) but misleading now.
- [ ] **`scripts/get_token.py:87`** uses `2>nul` (cmd.exe syntax) — Windows-only.


## Future Considerations 🤔

- [ ] **Consider cold-start warm-up between functions** — when `send_magic_link` runs (student logging in), it could ping `start_scenario` to warm it up since the student will use it next. Options: cross-function ping, Cloud Scheduler during class hours, or `--min-instances=1`. Tradeoff is complexity vs ~3s savings for the first student.


## Scenario Quality

- [ ] **Review each scenario for student success** — scenarios are currently theoretical and may set students up to fail. Go through each scenario and identify gaps, e.g. a scenario references "a report you sent" but the student never actually sent one and has no context. Consider generating simple supporting artifacts (e.g. a 3-line report) in the scenario instructions so students have concrete material to work with.


# Super Future / Scale-Up Considerations

Ideas that aren't needed now but would matter at scale.

## Reliable Email Delivery Queue

Currently, the reply email is sent inline after grading. If the process dies
between the Firestore write and `send_reply`, the student misses the email
(but can still see their grade in the portal).

**If reliable email delivery ever matters:**
- Write outbound emails to a Firestore `email_queue` collection after grading
- A separate worker (Cloud Function on a schedule or Firestore-triggered)
  picks up queued emails with retry logic
- Mark emails as `sent` after successful delivery
- This fully decouples grading from email delivery

## Grading Lease / Lock Pattern

Currently, Pub/Sub redelivery + the `status == 'graded'` idempotency guard
handle most failure cases. In a concurrent-worker scenario at scale, two
workers could redundantly grade the same attempt (wasteful but harmless).

**If this becomes a cost concern:**
- Set `status = 'grading'` with a `grading_started_at` timestamp before work
- Other workers skip attempts in `grading` state if the timestamp is recent
  (e.g. < 2 minutes)
- Stale `grading` entries are treated as dead and eligible for takeover