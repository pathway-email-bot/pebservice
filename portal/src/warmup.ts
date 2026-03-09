/**
 * Cloud Run Warm-Up
 *
 * Sends a fire-and-forget GET request to the /warmup endpoint on page load
 * to force a cold start before the user needs it, and to ensure the Gmail
 * push-notification watch subscription is active. Debounced via localStorage
 * so pings don't repeat within 5 minutes.
 *
 * Uses `mode: 'no-cors'` — the opaque response is ignored, but the request
 * is enough to spin up the Cloud Run container and trigger watch renewal.
 */

const CLOUD_FUNCTION_BASE_URL = 'https://peb-service-cnvksk3jla-uc.a.run.app';

const WARMUP_KEY = 'peb_last_warmup';
const WARMUP_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

const ENDPOINTS = [
    '/warmup',
];

export function warmUpServices(): void {
    try {
        const last = localStorage.getItem(WARMUP_KEY);
        if (last && Date.now() - parseInt(last, 10) < WARMUP_INTERVAL_MS) {
            return; // recently warmed — skip
        }

        // Fire-and-forget pings to each HTTP function
        for (const endpoint of ENDPOINTS) {
            fetch(`${CLOUD_FUNCTION_BASE_URL}${endpoint}`, { mode: 'no-cors' }).catch(() => {
                // Silently ignore — warm-up is best-effort
            });
        }

        localStorage.setItem(WARMUP_KEY, Date.now().toString());
    } catch {
        // localStorage may be unavailable (private browsing, etc.) — skip silently
    }
}
