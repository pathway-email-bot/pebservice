# Today's TODO (Feb 6, 2026)

## ✅ Priority 2: End-to-End Flow (IN PROGRESS)
See [implementation_plan.md](./implementation_plan.md)

---

## 📋 Priority 3: Email "FROM" Name Customization

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
