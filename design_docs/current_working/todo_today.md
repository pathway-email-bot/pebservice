# Today's TODO (Feb 6, 2026)

## 🔥 URGENT: Test IAM Secret Management Migration

**What was changed (Feb 6, 2026 - 16:50)**:
- ✅ Verified IAM permissions: Service account `687061619628-compute@developer.gserviceaccount.com` has `secretAccessor` role on all 4 secrets
- ✅ Updated `.github/workflows/deploy-service.yaml` to REMOVE `--set-secrets` flags
- ✅ Both functions now rely ONLY on IAM-based Secret Manager access (no env vars)

**CRITICAL - MUST TEST BEFORE NEXT USE**:
1. **Deployment will happen automatically** on next push to main (GitHub Actions)
2. **Monitor deployment**: https://github.com/pathway-email-bot/pebservice/actions
3. **Check function logs** for IAM success messages:
   ```bash
   gcloud functions logs read process_email --region=us-central1 --limit=50
   ```
   Look for: "Successfully fetched ... using IAM"
4. **Test end-to-end**:
   - Start a REPLY scenario from portal
   - Reply to the scenario email
   - Verify graded response arrives
5. **Verify no env vars**:
   ```bash
   gcloud functions describe process_email --region=us-central1 --gen2 --format="yaml(serviceConfig.environmentVariables)"
   ```
   Should NOT show GMAIL_* or OPENAI_API_KEY

**Rollback if needed**: See walkthrough.md in conversation artifacts

**Reference**: 
- [Walkthrough](file:///C:/Users/micha/.gemini/antigravity/brain/f8a7c5a2-015e-4073-ac0d-b4c881f83850/walkthrough.md)
- [Implementation Plan](file:///C:/Users/micha/.gemini/antigravity/brain/f8a7c5a2-015e-4073-ac0d-b4c881f83850/implementation_plan.md)

---

## ✅ Priority 2: End-to-End Flow (IN PROGRESS)
See [implementation_plan.md](./implementation_plan.md)

---

## � CRITICAL: Gmail Watch Management

**Issue**: Gmail push notifications (watch) expire every 7 days and must be manually renewed

**Current State**:
- Watch set up manually via `scripts/check_watch.py`
- Expires: 2026-02-13 15:30:28
- No automation for renewal

**Options**:
1. Cloud Scheduler + Cloud Function to auto-renew weekly
2. GitHub Actions cron job (requires stored bot credentials)
3. Manual renewal reminder (least ideal)

**Impact**: If watch expires, `process_email` function won't receive any notifications → emails won't be processed

**Next Steps**: Decide on automation strategy and implement before 2026-02-13

---

## �📋 Priority 3: Email "FROM" Name Customization

**Goal**: Make scenario emails appear from different people (e.g., "Bob Jones (Manager)")

**Notes**:
- Gmail API supports custom FROM display names via the `From` header
- Each scenario JSON already has `starter_sender_name` field
- Test spam folder behavior with changing names

---

## 📋 Priority 1: Scenario Management Infrastructure

**Goal**: Allow Tom Kerby to manage scenarios via JSON files without portal getting out of sync

**Options**:
1. Side-by-side repos - Portal assumes `../pebservice` exists
2. GitHub raw files - Portal fetches from raw.githubusercontent.com
3. Monorepo - student-portal becomes subdirectory of pebservice
4. Build-time sync - CI/CD copies scenarios at deploy

**Current workaround**: Hardcode scenario list in portal matching pebservice files
