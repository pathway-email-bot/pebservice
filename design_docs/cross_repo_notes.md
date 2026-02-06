# Cross-Repository Considerations

## 🔗 The Problem

We have **two repos** (`pebservice` and `student-portal`) sharing **one GCP project** (`pathway-email-bot-6543`). This creates some awkward situations:

1. **Shared Secrets**: Firebase config lives in GCP, but both repos may need access
2. **Shared Scripts**: `setup_gcloud.ps1` logic is identical between repos
3. **Shared Project ID**: Hardcoded in multiple places

---

## 🎯 Current Approach: Duplication with Documentation

For now, we **duplicate essential scripts** in each repo with clear documentation. This is pragmatic because:

1. **Independence**: Each repo can be cloned and set up without the other
2. **Simplicity**: No submodules, no npm packages, no complexity
3. **Explicitness**: Everything needed is visible in the repo

---

## 📁 Shared Patterns

### Project Constants
Both repos use:
- **Project ID**: `pathway-email-bot-6543`
- **Region**: `us-central1`
- **Source of Truth**: GCP Secret Manager

### Script Patterns
| Script Type | Purpose | Language |
|-------------|---------|----------|
| `setup_gcloud.ps1` | Configure gcloud CLI | PowerShell |
| `setup_venv.ps1` | Python virtual env (pebservice only) | PowerShell |
| `check_firebase.ps1` | Verify Firebase setup | PowerShell |
| `sync_secrets.py` | Sync from GCP Secret Manager | Python |

---

## 🚀 Future Improvements

### Option 1: Shared Config Package (npm)
- Publish `@pathway-email-bot/config` to npm (private or public)
- Contains project ID, region, shared types
- Both repos depend on it

### Option 2: Git Submodule
- Create `pathway-email-bot/shared-config` repo
- Include as submodule in both repos
- Contains scripts and constants

### Option 3: Monorepo
- Merge into single repo with folders
- Use Nx, Turborepo, or similar
- More complex but unified

---

## 📝 Current Decision

**Status**: Duplication with documentation (this file)

**Rationale**: 
- Project is small (2 repos)
- Overhead of shared package/submodule outweighs benefits
- Easy to refactor later if needed

**Maintenance Rule**: 
When updating shared patterns (like project ID), update BOTH repos and reference this document.
