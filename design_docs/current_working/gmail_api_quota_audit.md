# Gmail API Quota Audit — PEB Service

> All students interact through a single Gmail account: `pathwayemailbot@gmail.com` (free Gmail).
> All per-user quotas below apply to **this one account**, not per-student.

---

## 1. Quota Limits (Official Google Docs)

### Rate Limits (per minute)

| Scope | Limit |
|---|---|
| Per **project** | 1,200,000 quota units / min |
| Per **user** (OAuth) | **15,000 quota units / min** |

Since every API call uses the bot account's OAuth token, the **per-user** limit is the binding constraint.

### Daily Sending Limit

| Account Type | Sends / Day |
|---|---|
| **Free Gmail** | **500 messages / day** |
| Google Workspace | 2,000 messages / day |

> [!CAUTION]
> The free Gmail daily send cap of **500** is the hardest limit for PEB.
> Google may temporarily lock the account if this is exceeded.

### Quota Unit Cost per API Method

| Method | Units | Used In PEB? |
|---|---|---|
| `messages.send` | **100** | ✅ Reply to student + starter emails |
| `messages.get` | **5** | ✅ Fetch email content |
| `messages.list` | **5** | ✅ Fallback in `process_email` |
| `history.list` | **2** | ✅ Primary notification handler |
| `users.watch` | **100** | ✅ Push-notification renewal (≈weekly) |
| `users.getProfile` | 5 | ❌ Not used |

---

## 2. PEB Gmail API Call Map

### Flow A: `start_scenario` (student clicks "Start")

| Step | API Call | Units |
|---|---|---|
| Ensure watch (cached, rarely fires) | `users.watch` | 100 (amortized ≈0) |
| **REPLY scenarios only**: send starter email | `messages.send` | **100** |

- **INITIATE scenario**: **0 Gmail units** (no API calls needed)
- **REPLY scenario**: **100 Gmail units** (one `messages.send`)

### Flow B: `process_email` (student sends/replies to bot)

| Step | API Call | Units |
|---|---|---|
| Fetch history changes | `history.list` | **2** |
| Fetch each new message | `messages.get` × N | **5 × N** |
| *(fallback if no history)* | `messages.list` | **5** |
| *(fallback)* | `messages.get` | **5** |
| Grade + send reply email | `messages.send` | **100** |

- **Normal path (1 message):** `history.list` + `messages.get` + `messages.send` = **107 units**
- **Fallback path**: `history.list` + `messages.list` + `messages.get` + `messages.send` = **112 units**
- **No active scenario** (redirect reply): same cost, **107 units**

### Flow C: `ensure_watch` (distributed renewal)

- Fires at most once per ~6 days (7-day watch minus 24-hour buffer)
- Cost: **100 units**, fully amortized → negligible

---

## 3. Cost Per Complete Student Interaction

A student completes one scenario (start → send email → get graded reply):

| Scenario Type | API Calls | Total Units | Sends |
|---|---|---|---|
| **INITIATE** (student sends first) | `history.list` + `messages.get` + `messages.send` | **107** | **1** |
| **REPLY** (bot sends first) | `messages.send` (starter) + `history.list` + `messages.get` + `messages.send` (reply) | **207** | **2** |

---

## 4. Capacity Analysis

### Rate Limit: 15,000 units / minute

| Metric | INITIATE (107u) | REPLY (207u) | Blended* (165u) |
|---|---|---|---|
| Max interactions / min | **140** | **72** | **90** |
| Max interactions / hour | 8,400 | 4,320 | 5,400 |

*\*Blended assumes current mix: 4 INITIATE + 7 REPLY scenarios ≈ 64% REPLY*

> [!TIP]
> The per-minute rate limit is **not a concern** for a classroom-sized deployment. Even 90 simultaneous scenario completions per minute is far beyond realistic usage.

### Daily Send Limit: 500 sends / day (free Gmail) ⚠️

This is where the constraint actually bites:

| Scenario Type | Sends per Interaction | Max Interactions / Day |
|---|---|---|
| INITIATE | 1 | **500** |
| REPLY | 2 | **250** |
| Blended (64% REPLY) | ~1.64 | **~305** |

#### What does this mean for class sizes?

| Students | Scenarios each | Total interactions | Sends needed | Under 500 limit? |
|---|---|---|---|---|
| 30 | 11 (all) | 330 | ~541 | ❌ Exceeds |
| 30 | 8 | 240 | ~393 | ✅ OK |
| 25 | 11 | 275 | ~451 | ✅ Tight but OK |
| 20 | 11 | 220 | ~361 | ✅ OK |
| 50 | 5 | 250 | ~410 | ✅ OK |
| 50 | 11 | 550 | ~902 | ❌ Exceeds |

> [!WARNING]
> A single class of 30 students doing **all 11 scenarios in one day** would hit the send limit.
> In practice students spread work over days/weeks, so this is likely fine for a single class.
> Multiple concurrent classes would require mitigation.

---

## 5. Scaling Scenarios

### Scenario: One class of 30, all scenarios, over 1 week
- 330 total interactions → ~541 sends over 7 days → **~77 sends/day** ✅ Easily fine

### Scenario: 3 classes of 30, all scenarios, over 2 weeks
- 990 total interactions → ~1,624 sends over 14 days → **~116 sends/day** ✅ Fine

### Scenario: Assignment due date crunch (30 students, 5 scenarios in one evening)
- 150 interactions → ~246 sends in a few hours → ✅ **Fine** (well under 500)

### Scenario: 100 students all active on same day
- If each does ~3 scenarios: 300 interactions → ~492 sends → ⚠️ **Razor thin**
- If each does ~5 scenarios: 500 interactions → ~820 sends → ❌ **Over limit**

---

## 6. Verdict & Action Item

### Current Capacity: Sufficient for 1 class section

For a single class of 20–30 students working through scenarios over a few weeks, the free Gmail account is adequate. The daily send limit of 500 won't be hit unless everyone crams all scenarios into a single day.

### If we hit the 500 sends/day limit

Two practical options:

| Option | Effort | Effect |
|---|---|---|
| **Upgrade to Google Workspace** (~$6/mo for 1 bot account) | Low | Daily send limit → **2,000** (4× headroom), also improves spam deliverability |
| **Multiple free Gmail bot accounts** — round-robin sends across 2–3 accounts | Medium | Multiplies all limits linearly (2 accounts = 1,000/day, 3 = 1,500/day) |

> [!IMPORTANT]
> No action needed now. Revisit if scaling beyond ~30 active students per day or if send failures appear in Cloud Function logs.

