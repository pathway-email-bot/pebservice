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
