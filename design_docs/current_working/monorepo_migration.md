# Monorepo Migration Plan

Merge `student-portal` into `pebservice` as a monorepo.

## Target Structure

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

---

## Migration Steps

### Step 1: Restructure pebservice
1. Rename `src/` → `service/`
2. Update `deploy.yaml` to reference `service/` directory
3. Update any imports/paths in Python code

### Step 2: Copy student-portal content
1. Copy `student-portal/src/` → `pebservice/portal/src/`
2. Copy `student-portal/package.json`, `tsconfig.json`, `index.html`
3. Copy `student-portal/public/`
4. Merge `student-portal/design_docs/` into `pebservice/design_docs/`

### Step 3: Create portal deploy workflow
```yaml
# .github/workflows/deploy-portal.yaml
name: Deploy Portal to GitHub Pages

on:
  push:
    branches: [main]
    paths: ['portal/**']  # Only trigger on portal changes
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd portal && npm ci && npm run build
      - uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./portal/dist
```

### Step 4: Update existing service workflow
- Rename to `deploy-service.yaml`
- Add path filter: `paths: ['service/**']`
- Update `--source=service` in gcloud command

### Step 5: Update portal vite config
Set `base: '/pebservice/'` for GitHub Pages subdirectory hosting.

### Step 6: Archive student-portal repo
After confirming everything works, archive or delete the separate repo.

---

## Files to Update

| File | Change |
|------|--------|
| `deploy.yaml` → `deploy-service.yaml` | Change `--source=src` to `--source=service`, add path filter |
| `portal/vite.config.ts` | Add `base: '/pebservice/'` |
| Python imports | Should work (relative imports within `service/`) |

## Risks
- Git history for student-portal won't be preserved (copy, not merge)
- Need to update any hardcoded paths

## Decision Needed
Proceed with migration?
