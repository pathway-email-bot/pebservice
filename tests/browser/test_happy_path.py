"""
Browser E2E test: full happy-path flow through the student portal.

Uses Playwright + pytest to drive a real browser through:
  1. Login — enter test email → magic link sent
  2. Get magic link — Gmail API reads the sign-in email from inbox
  3. Navigate to magic link — browser follows link → redirects to scenarios
  4. Enter name — fill the first-time name modal
  5. Start an initiate scenario — expand drawer → click "Start"
  6. Send email — Gmail API sends a test email to the bot
  7. Wait for score — poll until grading results appear in the UX

Screenshots and logs are saved to tests/browser/output/ at each step for visual debugging.

Run:
  pip install playwright pytest-playwright
  playwright install chromium
  python -m pytest tests/browser/test_happy_path.py -v --timeout=180

Prerequisites:
  - GCP credentials (test-runner-key.secret.json or GOOGLE_APPLICATION_CREDENTIALS)
  - Gmail OAuth secrets in Secret Manager (gmail-client-id, gmail-client-secret,
    gmail-refresh-token-test)

Cost: ~$0.01 per run (1 OpenAI API call for grading)
"""

import os
import re
import time
import uuid
import base64
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

# ── Config ───────────────────────────────────────────────────────────

PROJECT_ID = "pathway-email-bot-6543"
TEST_EMAIL = "michaeltreynolds.test@gmail.com"
BOT_EMAIL = "pathwayemailbot@gmail.com"

# Default to production (GitHub Pages); override with PORTAL_URL for local dev
PORTAL_URL = os.environ.get("PORTAL_URL", "https://pathway-email-bot.github.io/pebservice/")

# Which scenario to run (must be interaction_type=initiate)
SCENARIO_ID = "missed_remote_standup"

POLL_TIMEOUT = 120  # seconds to wait for grading
POLL_INTERVAL = 5   # seconds between polls
MAGIC_LINK_WAIT = 15  # seconds — email arrives in ~5s, this gives 3x margin

# Output directory (tests/browser/output/)
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
LOG_FILE = OUTPUT_DIR / "test_log.txt"


# ── Helpers ──────────────────────────────────────────────────────────


def _clear_output() -> None:
    """Remove previous test output so only current run is visible."""
    if OUTPUT_DIR.exists():
        import shutil
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(exist_ok=True)


_test_start: float = 0.0  # set at test start for elapsed time


def _log(msg: str) -> None:
    """Append a timestamped line with elapsed time to the test log file."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%H:%M:%S")
    elapsed = f"+{time.time() - _test_start:.1f}s" if _test_start else ""
    line = f"[{ts}] [{elapsed:>8s}] {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"  {msg}")


def _snap(page: Page, name: str) -> None:
    """Save a screenshot, page HTML, and full browser state for this step."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%H%M%S")

    # Screenshot
    img_path = OUTPUT_DIR / f"{ts}_{name}.png"
    page.screenshot(path=str(img_path), full_page=True)

    # Page HTML
    html_path = OUTPUT_DIR / f"{ts}_{name}.html"
    html_path.write_text(page.content(), encoding="utf-8")

    # State dump
    _log(f"── {name} ──")
    _log(f"  📸 {img_path.name}")
    _log(f"  URL: {page.url}")

    # LocalStorage
    try:
        ls = page.evaluate("""() => {
            const items = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                items[k] = localStorage.getItem(k);
            }
            return items;
        }""")
        _log(f"  localStorage: {ls}")
    except Exception as e:
        _log(f"  localStorage: (error: {e})")

    # Console errors (if any were captured)
    _log(f"  HTML saved: {html_path.name}")


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def gmail():
    """Authenticated Gmail service for the test account."""
    from tests.helpers.gmail_helpers import get_test_gmail_service
    return get_test_gmail_service()


@pytest.fixture(autouse=True)
def _clean_test_account():
    """
    Acquire a mutex, delete the test user's Firestore data, and release after test.

    This ensures:
      - Parallel test pipelines don't corrupt each other's state
      - The test exercises the real new-user flow (name modal appears naturally)
      - Attempt history doesn't grow unbounded from CI runs
    """
    from tests.helpers.firestore_helpers import (
        get_firestore_db, test_user_lock, delete_user_document,
    )
    db = get_firestore_db()
    with test_user_lock(db, log=_log):
        deleted = delete_user_document(db, TEST_EMAIL)
        _log(f"Cleaned test account (deleted {deleted} attempts + user doc)")
        yield  # lock held during entire test


def _find_magic_link(gmail_service, timeout: int = MAGIC_LINK_WAIT, sent_after: float = 0) -> str:
    """
    Poll Gmail inbox for the Firebase magic link email.
    Returns the sign-in URL extracted from the HTML email body.

    Args:
        sent_after: epoch timestamp — only consider emails sent after this time.
                    Prevents picking up stale links from previous test runs.
    """
    from html import unescape
    from bs4 import BeautifulSoup
    from googleapiclient.errors import HttpError

    start = time.time()
    first_poll = True
    while time.time() - start < timeout:
        try:
            results = gmail_service.users().messages().list(
                userId="me",
                q=f'from:{BOT_EMAIL} subject:"Sign in to Pathway Email Bot"',
                maxResults=5,
                includeSpamTrash=True,
            ).execute()
        except HttpError as e:
            if e.resp.status in (401, 403):
                raise RuntimeError(
                    f"Gmail API auth failed (HTTP {e.resp.status}). "
                    f"Check that test account OAuth tokens in Secret Manager are valid."
                ) from e
            raise

        messages = results.get("messages", [])
        if first_poll:
            from datetime import datetime, timezone
            cutoff_utc = datetime.fromtimestamp(sent_after, tz=timezone.utc).strftime("%H:%M:%S")
            _log(f"  Gmail poll: {len(messages)} candidates (cutoff={cutoff_utc} UTC)")
            for m in messages:
                meta = gmail_service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["Subject"],
                ).execute()
                ts = int(meta.get("internalDate", "0")) / 1000
                ts_utc = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")
                delta = ts - sent_after
                subj = ""
                for h in meta.get("payload", {}).get("headers", []):
                    if h["name"] == "Subject":
                        subj = h["value"][:50]
                _log(f"    {ts_utc} UTC (delta={delta:+.0f}s) {subj}")
            first_poll = False

        for msg_meta in messages:
            msg = gmail_service.users().messages().get(
                userId="me", id=msg_meta["id"], format="full",
            ).execute()

            # Only consider emails sent AFTER we triggered the magic link
            internal_date_ms = int(msg.get("internalDate", "0"))
            email_epoch = internal_date_ms / 1000
            if email_epoch < sent_after:
                continue

            # Find the text/html part (plain text has no URL)
            html_body = _get_html_body(msg)
            if not html_body:
                continue

            # Parse HTML and find the sign-in link
            soup = BeautifulSoup(html_body, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = unescape(a_tag["href"])  # decode &amp; → &
                if "mode=signIn" in href:
                    return href

        time.sleep(2)

    raise TimeoutError(
        f"No magic link email found within {timeout}s. "
        f"Check that Firebase email link auth is enabled and {TEST_EMAIL} is valid."
    )


def _get_html_body(msg: dict) -> str:
    """Extract text/html body from a Gmail API message (where the magic link lives)."""
    payload = msg.get("payload", {})

    # Simple single-part HTML message
    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8")

    # Multipart: look for text/html
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8")

    return ""


# ── Test ─────────────────────────────────────────────────────────────


class TestHappyPath:
    """
    Full browser E2E: login → name → start scenario → send email → see score.
    """

    def test_full_flow(self, page: Page, gmail):
        global _test_start
        _test_start = time.time()
        _clear_output()

        # Capture browser console messages to the log
        page.on("console", lambda msg: _log(f"  [console.{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: _log(f"  [PAGE ERROR] {err}"))

        # ── Step 1: Navigate to portal and enter email ───────────
        page.goto(PORTAL_URL)
        page.wait_for_load_state("networkidle")
        _snap(page, "01_login_page")

        email_input = page.locator("#email")
        email_input.fill(TEST_EMAIL)

        send_time = time.time() - 5  # record BEFORE clicking, with 5s buffer for clock skew
        page.locator("#submit-btn").click()

        # Should see confirmation message
        expect(page.locator(".message-success")).to_be_visible(timeout=10000)
        _snap(page, "02_magic_link_sent")

        # ── Step 2: Get magic link from Gmail ────────────────────
        magic_link = _find_magic_link(gmail, sent_after=send_time)
        assert "mode=signIn" in magic_link, f"Unexpected link format: {magic_link}"

        _log(f"Magic link: {magic_link}")

        # ── Step 3: Navigate to magic link ───────────────────────
        # Firebase action URL redirects to the continueUrl with auth params.
        # Use domcontentloaded (not networkidle) because Firebase keeps connections open.
        page.goto(magic_link, wait_until="domcontentloaded")
        _snap(page, "03a_firebase_action_page")

        # Wait for Firebase to redirect to the portal (match the actual domain, not URL params)
        page.wait_for_url("https://pathway-email-bot.github.io/**", timeout=15000)
        page.wait_for_load_state("domcontentloaded")

        # Log browser state for debugging
        _snap(page, "03b_after_redirect")

        # Should redirect to scenarios page (may take a moment for auth)
        expect(page.locator(".scenarios-container")).to_be_visible(timeout=15000)
        _snap(page, "04_scenarios_page")

        # ── Step 4: Enter name (name modal shows for new users) ────────
        # We deleted the user document in _clean_test_account, so this is
        # a real new-user flow — the name modal appears naturally.
        # Wait for the Firestore listener to fire (no user doc → null → modal).
        import time as _time
        _time.sleep(2)  # allow Firestore listener to fire
        name_modal = page.locator(".name-modal-overlay")
        if name_modal.is_visible():
            _snap(page, "05a_name_modal")
            page.locator("#first-name-input").fill("SarahTestBot")
            page.locator("#name-submit-btn").click()
            expect(name_modal).to_be_hidden(timeout=5000)
            _snap(page, "05b_name_submitted")
        else:
            _log("Name modal not shown (name already set). Skipping.")

        # ── Step 5: Start a scenario ─────────────────────────────
        # New UI: cards are collapsed. Click header to expand drawer, then Start button.
        scenario_id = SCENARIO_ID  # default target
        card_header = page.locator(f'.scenario-header-clickable[data-scenario-id="{SCENARIO_ID}"]')
        card_header.click()
        _log(f"Expanding drawer for: {SCENARIO_ID}")

        # Wait for Start button to appear in the expanded drawer
        start_btn = page.locator(f'.start-btn[data-scenario-id="{SCENARIO_ID}"]')
        expect(start_btn).to_be_visible(timeout=5000)
        _snap(page, "06_drawer_expanded")

        # Click Start
        start_btn.click()
        _log("Clicked Start button — waiting for Cloud Function response...")

        # Wait for the active drawer to appear (loading completes).
        # The start_scenario Cloud Function may take 10-20s for initiate scenarios
        # (it calls OpenAI to generate the starter email).
        expect(page.locator(".scenario-card.active")).to_be_visible(timeout=30000)
        _snap(page, "07_scenario_started")

        # ── Step 6: Send email via Gmail API ─────────────────────
        from tests.helpers.gmail_helpers import send_email

        tag = uuid.uuid4().hex[:6]
        body_text = (
            "Hi team,\n\n"
            "I apologize for missing the standup this morning. I overslept due "
            "to a late night debugging a production issue.\n\n"
            "Yesterday: Completed the API endpoint refactoring.\n"
            "Today: Planning to finish the database migration script.\n"
            "Blockers: Need staging database credentials.\n\n"
            "Sorry for the inconvenience.\n\n"
            "Best regards"
        )

        send_email(
            gmail,
            from_email=TEST_EMAIL,
            to_email=BOT_EMAIL,
            subject=f"Re: Email Practice - {scenario_id} [test-{tag}]",
            body=body_text,
        )
        _snap(page, "08_email_sent")

        # ── Step 7: Wait for score to appear in UI ───────────────
        # The score badge should appear on the card once grading completes.
        # Firestore real-time listener auto-updates the DOM.
        # Note: a "Score pending..." badge may be visible immediately, so we
        # check for actual score content (contains "/") not just visibility.
        score_locator = page.locator(
            f'.scenario-card[data-scenario-id="{scenario_id}"] .score-badge'
        )

        start_time = time.time()
        while time.time() - start_time < POLL_TIMEOUT:
            if score_locator.is_visible():
                text = score_locator.inner_text()
                if "/" in text:
                    _log(f"Score appeared: {text}")
                    break
            time.sleep(POLL_INTERVAL)
            if int(time.time() - start_time) % 10 == 0:
                _snap(page, f"09_waiting_{int(time.time() - start_time)}s")
        else:
            _snap(page, "09_TIMEOUT_no_score")
            pytest.fail(
                f"Score did not appear within {POLL_TIMEOUT}s. "
                f"Check that grading pipeline is working."
            )

        # ── Step 8: Assert score and feedback ────────────────────
        score_text = score_locator.inner_text()
        assert "/" in score_text, f"Expected score format 'X/Y', got: {score_text}"

        # Verify feedback section is also present
        feedback = page.locator(
            f'.scenario-card[data-scenario-id="{scenario_id}"] .grading-results'
        )
        expect(feedback).to_be_visible(timeout=5000)
        _snap(page, "10_DONE_score_visible")
