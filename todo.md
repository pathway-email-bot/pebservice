better logging use a decorator that logs functions as a whole and trace logging additionally with trace logging that works with the state set by the decorator to know what file/method it is being run from.

**LOGGING: Structured logging with attempt_id propagation**
- Every log line should include the attempt_id (UUID) — not just on key events
- Include request metadata: sender email, email subject, timestamps, scenario_id
- Decorator-based tracing: function entry/exit, duration, which scenario/rubric was used
- Error telemetry: exception stack traces with full context for diagnosing production issues
- Goal: be able to debug any issue from logs alone without needing to reproduce locally

test plan for changes 

scripts directory becomes a skills directory with documentation.

General rules:
- always create a script to check things in external systems or when a review is requested to access other things with credentials so they can be approved once for future use.


Agents are frequently crashing need a persistent repo-centric way to store the conversation. Not in some hidden files outside of git.

Need some setup steps for a repo or working with a repo
- python venv (or equivalent for the repo)
- python requirements.txt
- gcloud
- gh
- or any tools that are needed to work with this project...

Maybe should have some script to check if the service is running, describe it, and see if we are ready to work on it.

Need a test email and have it run as part of CI/CD

Need to make a list of rules for agents to follow in general (good practices like testing, developer inner loop improvements, creating scripts instead of directly calling external systems, keeping an ongoing log of actions in the repo)

**SECURITY: Migrate GitHub Actions auth to Workload Identity Federation**
- Current: Using long-lived service account key stored in GCP_SA_KEY secret
- Better: Use Workload Identity Federation (WIF) with OIDC tokens
- Benefits: No long-lived credentials, automatic rotation, better auditability
- Steps: Set up WIF provider in GCP, configure GitHub as OIDC provider, update deploy.yaml workflow

---------- EMAIL AGENT ---------------
The response new too much context. It did not scope it's understanding to the users email. This is not good. I sent a test email and it said "Thanks for telling me about the power outage"...

A/B test Gemini vs GPT-4o for email quality. Gemini 2.0 Flash is ~25x cheaper than GPT-4o. Run the same scenarios through both and compare side-by-side: starter email generation, counterpart replies, and grading (JSON output + rubric scoring). Could use Flash for generation/replies and keep GPT-4o (or Gemini 2.5 Pro) only for grading where nuance matters most. LangChain swap is easy — just use langchain_google_genai.

