/**
 * Login Page Component
 * 
 * Renders the email login form with magic link authentication.
 */

import { sendMagicLink } from '../auth';

export function renderLoginPage(container: HTMLElement): void {
  container.innerHTML = `
    <div class="login-page">
      <div class="card login-card">
        <div class="welcome-icon">📧</div>
        <h1>Welcome to the BYU Pathways Email Tutor!</h1>
        <p class="subtitle">Practice your professional email skills with real scenarios</p>
        
        <form id="login-form">
          <div class="form-group">
            <label for="email">Your Email Address</label>
            <input 
              type="email" 
              id="email" 
              name="email" 
              placeholder="student@example.com"
              required
              autocomplete="email"
            />
          </div>
          
          <button type="submit" class="btn btn-primary" id="submit-btn">
            Send Login Link
          </button>
        </form>
        
        <p class="text-muted mt-md" style="font-size: 0.9rem;">
          We'll send you a secure link to sign in — no password needed.
        </p>
      </div>
    </div>
  `;

  // Set up form handling
  const form = document.getElementById('login-form') as HTMLFormElement;
  const emailInput = document.getElementById('email') as HTMLInputElement;
  const submitBtn = document.getElementById('submit-btn') as HTMLButtonElement;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = emailInput.value.trim();

    if (!email) return;

    // Disable button and show loading state
    submitBtn.disabled = true;
    submitBtn.textContent = 'Sending...';

    try {
      await sendMagicLink(email);

      // Show success message
      showMessage(container, 'success', `✓ Check your email! We sent a login link to ${email}`);

      // Show prominent spam warning after sending
      showSpamWarning(container);

      // Clear the form
      emailInput.value = '';

    } catch (error) {
      console.error('Login error:', error);

      // Show the actual error message from auth.ts
      const message = error instanceof Error
        ? error.message
        : 'Something went wrong. Please try again.';

      showMessage(container, 'error', message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send Login Link';
    }
  });
}

function showMessage(container: HTMLElement, type: 'success' | 'error' | 'info', message: string): void {
  // Remove any existing message
  const existing = container.querySelector('.message');
  if (existing) existing.remove();

  // Create and insert message
  const messageEl = document.createElement('div');
  messageEl.className = `message message-${type}`;
  messageEl.textContent = message;

  const form = container.querySelector('#login-form');
  form?.parentNode?.insertBefore(messageEl, form);
}

function showSpamWarning(container: HTMLElement): void {
  // Remove any existing spam warning
  const existing = container.querySelector('.spam-warning');
  if (existing) existing.remove();

  const warningEl = document.createElement('div');
  warningEl.className = 'spam-warning';
  warningEl.innerHTML = `
        <p><strong>⚠️ Important: Check your spam/junk folder!</strong></p>
        <p>The sign-in email may land in spam. If it does:</p>
        <ol>
            <li>Open the email in your spam folder</li>
            <li>Click <strong>"Not spam"</strong> or <strong>"Report not spam"</strong></li>
            <li>Add <em>noreply@pathway-email-bot-6543.firebaseapp.com</em> to your contacts</li>
        </ol>
        <p style="margin-bottom:0">This also helps future emails from Pathway Email Bot reach your inbox.</p>
    `;

  // Insert after the success message
  const successMsg = container.querySelector('.message-success');
  if (successMsg) {
    successMsg.parentNode?.insertBefore(warningEl, successMsg.nextSibling);
  } else {
    const form = container.querySelector('#login-form');
    form?.parentNode?.insertBefore(warningEl, form);
  }
}
