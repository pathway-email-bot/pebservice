/**
 * Feedback Modal Component
 *
 * Renders a discreet "Feedback?" link and a modal with star rating + message.
 * If the user is logged in, their email is auto-filled; otherwise they can
 * optionally provide one. Submits to the submit_feedback Cloud Function.
 */

import { getCurrentUser } from './auth';

const CLOUD_FUNCTION_BASE_URL = 'https://us-central1-pathway-email-bot-6543.cloudfunctions.net';

// Capture recent console errors for context
const _recentErrors: string[] = [];
const _originalConsoleError = console.error;
console.error = (...args: any[]) => {
    _recentErrors.push(args.map(a => String(a)).join(' '));
    if (_recentErrors.length > 10) _recentErrors.shift();
    _originalConsoleError.apply(console, args);
};
window.addEventListener('error', (e) => {
    _recentErrors.push(`${e.message} (${e.filename}:${e.lineno})`);
    if (_recentErrors.length > 10) _recentErrors.shift();
});

/** Detect which page is currently showing */
function getCurrentPage(): string {
    const app = document.querySelector('#app');
    if (app?.querySelector('.scenarios-page')) return 'scenarios';
    if (app?.querySelector('.login-page')) return 'login';
    return 'unknown';
}

/**
 * Inject the persistent "Feedback?" link into the page.
 * Safe to call multiple times — will not duplicate.
 */
export function injectFeedbackLink(): void {
    if (document.getElementById('feedback-link')) return;

    const link = document.createElement('button');
    link.id = 'feedback-link';
    link.className = 'feedback-link';
    link.textContent = 'Feedback?';
    link.setAttribute('aria-label', 'Send feedback');
    link.addEventListener('click', openFeedbackModal);
    document.body.appendChild(link);
}

/** Open the feedback modal */
function openFeedbackModal(): void {
    // Prevent duplicates
    if (document.getElementById('feedback-modal-overlay')) return;

    const user = getCurrentUser();
    const isLoggedIn = !!user;

    const emailFieldHTML = isLoggedIn
        ? '' // Email auto-filled from auth
        : `
        <div class="form-group">
            <label for="feedback-email">Your Email (optional)</label>
            <input type="email" id="feedback-email" placeholder="student@example.com" autocomplete="email" />
        </div>`;

    const overlay = document.createElement('div');
    overlay.id = 'feedback-modal-overlay';
    overlay.className = 'feedback-modal-overlay';
    overlay.innerHTML = `
        <div class="feedback-modal" role="dialog" aria-label="Send feedback">
            <div class="feedback-modal-header">
                <h2>Send Feedback</h2>
                <button class="feedback-close-btn" aria-label="Close">&times;</button>
            </div>
            <div class="feedback-modal-body">
                <div class="star-rating" role="group" aria-label="Rating">
                    <span class="star-label">How's your experience?</span>
                    <div class="stars">
                        ${[1, 2, 3, 4, 5].map(n =>
        `<button class="star" data-value="${n}" aria-label="${n} star${n > 1 ? 's' : ''}">
                                <svg viewBox="0 0 24 24" width="32" height="32">
                                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                                </svg>
                            </button>`
    ).join('')}
                    </div>
                </div>
                ${emailFieldHTML}
                <div class="form-group">
                    <label for="feedback-message">Message</label>
                    <textarea id="feedback-message" rows="3" placeholder="What's on your mind?" required></textarea>
                </div>
                <div id="feedback-status" class="feedback-status" style="display:none;"></div>
                <button id="feedback-send-btn" class="btn btn-primary feedback-send-btn" disabled>
                    <span>Send</span>
                    <svg class="send-icon" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                    </svg>
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    // --- Wire up interactions ---
    const closeBtn = overlay.querySelector('.feedback-close-btn') as HTMLButtonElement;
    const sendBtn = document.getElementById('feedback-send-btn') as HTMLButtonElement;
    const messageInput = document.getElementById('feedback-message') as HTMLTextAreaElement;
    const stars = overlay.querySelectorAll<HTMLButtonElement>('.star');

    let selectedStars = 0;

    // Close handlers
    closeBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });
    document.addEventListener('keydown', escHandler);

    function escHandler(e: KeyboardEvent) {
        if (e.key === 'Escape') closeModal();
    }

    function closeModal() {
        overlay.classList.add('closing');
        setTimeout(() => {
            overlay.remove();
            document.removeEventListener('keydown', escHandler);
        }, 200);
    }

    // Star rating
    stars.forEach(star => {
        star.addEventListener('mouseenter', () => highlightStars(parseInt(star.dataset.value!)));
        star.addEventListener('mouseleave', () => highlightStars(selectedStars));
        star.addEventListener('click', () => {
            selectedStars = parseInt(star.dataset.value!);
            highlightStars(selectedStars);
            updateSendButton();
        });
    });

    function highlightStars(count: number) {
        stars.forEach(s => {
            const val = parseInt(s.dataset.value!);
            s.classList.toggle('active', val <= count);
        });
    }

    // Enable send when stars + message provided
    messageInput.addEventListener('input', updateSendButton);
    function updateSendButton() {
        sendBtn.disabled = selectedStars === 0 || messageInput.value.trim() === '';
    }

    // Submit
    sendBtn.addEventListener('click', async () => {
        if (sendBtn.disabled) return;

        const email = isLoggedIn
            ? user!.email || ''
            : (document.getElementById('feedback-email') as HTMLInputElement)?.value?.trim() || '';

        const payload = {
            message: messageInput.value.trim(),
            stars: selectedStars,
            page: getCurrentPage(),
            email,
            consoleErrors: _recentErrors.slice(),
        };

        sendBtn.disabled = true;
        sendBtn.querySelector('span')!.textContent = 'Sending...';
        hideStatus();

        // DEV mock
        if (import.meta.env.DEV) {
            console.info('[DEV MOCK] submit_feedback', payload);
            await new Promise(r => setTimeout(r, 800));
            showStatus('success', '✓ Thanks for your feedback!');
            setTimeout(closeModal, 1500);
            return;
        }

        try {
            const response = await fetch(`${CLOUD_FUNCTION_BASE_URL}/submit_feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                if (response.status === 429) {
                    showStatus('error', err.error || 'Please wait a moment before sending more feedback.');
                } else {
                    showStatus('error', err.error || 'Something went wrong. Please try again.');
                }
                sendBtn.disabled = false;
                sendBtn.querySelector('span')!.textContent = 'Send';
                return;
            }

            showStatus('success', '✓ Thanks for your feedback!');
            setTimeout(closeModal, 1500);

        } catch (error) {
            console.error('Feedback submit error:', error);
            showStatus('error', 'Network error. Please try again.');
            sendBtn.disabled = false;
            sendBtn.querySelector('span')!.textContent = 'Send';
        }
    });

    function showStatus(type: 'success' | 'error', msg: string) {
        const el = document.getElementById('feedback-status')!;
        el.textContent = msg;
        el.className = `feedback-status feedback-status-${type}`;
        el.style.display = 'block';
    }

    function hideStatus() {
        const el = document.getElementById('feedback-status');
        if (el) el.style.display = 'none';
    }

    // Focus message input
    setTimeout(() => messageInput.focus(), 100);
}
