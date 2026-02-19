# PEB Service – Todo

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