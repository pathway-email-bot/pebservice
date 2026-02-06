# Monorepo Migration - ✅ COMPLETED

**Status**: Migration completed on 2026-02-06

## What Was Done

```
pebservice/
├── .github/workflows/
│   ├── deploy-service.yaml    # Cloud Functions (existing, renamed)
│   └── deploy-portal.yaml     # GitHub Pages (new)
├── service/                   # Renamed from src/
│   ├── main.py
│   ├── email_agent/
│   └── requirements.txt
├── portal/                    # Moved from student-portal/
│   ├── src/
│   ├── package.json
│   ├── index.html
│   └── tsconfig.json
├── design_docs/               # Merged from both repos
├── readme.md
└── todo.md
```

## GitHub Pages URL

After migration: `https://pathway-email-bot.github.io/pebservice/`

## GitHub Pages URL

Portal is live at: `https://pathway-email-bot.github.io/pebservice/`

---

## Completed Steps

### 1. ✅ Restructured pebservice
- Renamed `src/` → `service/`
- Updated `deploy.yaml` → `deploy-service.yaml` with path filter `service/**`
- Updated gcloud deploy command to use `--source=service`

### 2. ✅ Migrated student-portal content
- Copied `student-portal/src/` → `pebservice/portal/src/`
- Copied `package.json`, `tsconfig.json`, `index.html`, `public/`
- Merged `design_docs/` from both repos

### 3. ✅ Created portal deployment
- Created `.github/workflows/deploy-portal.yaml` for GitHub Pages
- Path filter: `portal/**` (only deploys when portal changes)
- Created `portal/vite.config.ts` with `base: '/pebservice/'`

### 4. ✅ Updated configuration
- Updated `.gitignore` for portal build artifacts
- Updated `readme.md` with monorepo structure

### 5. ✅ Cleanup
- Deleted GitHub repo `pathway-email-bot/student-portal`
- Made `pebservice` repo public (enables free GitHub Pages)
- Enabled GitHub Pages with GitHub Actions deployment

---

## Final Structure

```
pebservice/
├── .github/workflows/
│   ├── deploy-service.yaml    # Triggers on service/** changes
│   └── deploy-portal.yaml     # Triggers on portal/** changes
├── service/                   # Cloud Functions (Python)
│   ├── main.py
│   ├── email_agent/
│   └── requirements.txt
├── portal/                    # Student portal (TypeScript/Vite)
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   └── index.html
├── design_docs/               # Merged documentation
└── readme.md
```

---

## Next Steps

With the monorepo complete, proceed to implement the end-to-end student portal flow:
1. Implement `sendScenarioEmail` Cloud Function
2. Update `main.py` for Firestore-based scenario matching
3. Update portal to fetch scenarios and integrate with Firestore
4. Deploy Firestore security rules

See `implementation_plan.md` for details.

