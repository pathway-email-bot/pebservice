import './style.css';
import { renderLoginPage } from './pages/login';
import { renderScenariosPage } from './pages/scenarios';
import { onAuthChange, completeMagicLinkSignIn } from './auth';
import { injectFeedbackLink } from './feedback';

/**
 * Routing is auth-state driven, not URL-path driven.
 *
 *   Authenticated   → scenarios page
 *   Not authenticated → login page
 *
 * The URL is ALWAYS the root (/pebservice/ in prod, / in dev).
 * There are no subpath routes like /scenarios — the page shown
 * depends entirely on Firebase Auth state (persisted in IndexedDB).
 *
 * Why this matters:
 *   - Refresh works: URL stays at root, Firebase re-hydrates auth → same page renders.
 *   - No 404 risk: GitHub Pages only needs to serve index.html from the root.
 *   - Magic link redirect goes to root too (see auth.ts getActionCodeSettings).
 *   - No need for 404.html SPA hacks on GitHub Pages.
 */
const app = document.querySelector<HTMLDivElement>('#app')!;

async function boot() {
    // Inject the feedback link once (persists across page transitions)
    injectFeedbackLink();

    // If returning from a magic link, complete the sign-in first
    try {
        const user = await completeMagicLinkSignIn();
        if (user) {
            console.log('Signed in via magic link:', user.email);
        }
    } catch (error) {
        console.error('Magic link sign-in error:', error);
    }

    // Listen for auth state and render accordingly
    onAuthChange((user) => {
        if (user) {
            renderScenariosPage(app);
        } else {
            renderLoginPage(app);
        }
    });
}

boot();
