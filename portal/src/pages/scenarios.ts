/**
 * Scenarios Page Component
 * 
 * Displays the list of available email practice scenarios.
 */

import { completeMagicLinkSignIn, onAuthChange, logout, getCurrentUser } from '../auth';
import type { User } from 'firebase/auth';

export async function renderScenariosPage(container: HTMLElement): Promise<void> {
    // Check if we're returning from a magic link
    try {
        const user = await completeMagicLinkSignIn();
        if (user) {
            console.log('Signed in via magic link:', user.email);
        }
    } catch (error) {
        console.error('Magic link sign-in error:', error);
    }

    // Render based on auth state
    const currentUser = getCurrentUser();

    if (currentUser) {
        renderAuthenticatedView(container, currentUser);
    } else {
        renderUnauthenticatedView(container);
    }

    // Listen for auth changes
    onAuthChange((user) => {
        if (user) {
            renderAuthenticatedView(container, user);
        } else {
            renderUnauthenticatedView(container);
        }
    });
}

function renderAuthenticatedView(container: HTMLElement, user: User): void {
    container.innerHTML = `
    <div class="scenarios-page">
      <header class="page-header">
        <h1>📧 Email Practice Scenarios</h1>
        <div class="user-info">
          <span>Welcome, ${user.email}</span>
          <button id="logout-btn" class="btn btn-secondary">Sign Out</button>
        </div>
      </header>
      
      <main class="scenarios-container">
        <p class="subtitle">Choose a scenario to practice your professional email skills</p>
        
        <div class="scenario-list">
          ${renderScenarioCard(1, 'Introduce yourself as a new member of a team', 'available')}
          ${renderScenarioCard(2, 'Explain why you were late for standup', 'available')}
          ${renderScenarioCard(3, 'Clarify a vague task assigned from a manager', 'available')}
          ${renderScenarioCard(4, 'Correct an error found in a report', 'available')}
          ${renderScenarioCard(5, 'Reschedule a meeting due to a conflicting appointment', 'available')}
          ${renderScenarioCard(6, 'Respond to feedback that you have slow responses', 'available')}
        </div>
      </main>
    </div>
  `;

    // Add logout handler
    document.getElementById('logout-btn')?.addEventListener('click', async () => {
        await logout();
        window.location.href = '/';
    });

    // Add start button handlers
    document.querySelectorAll('.start-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const scenarioId = (e.target as HTMLElement).dataset.scenarioId;
            alert(`Starting scenario #${scenarioId}! (Coming soon)`);
        });
    });
}

function renderScenarioCard(id: number, title: string, status: 'available' | 'pending' | 'completed'): string {
    const statusBadge = status === 'completed'
        ? '<span class="badge badge-success">✓ Completed</span>'
        : status === 'pending'
            ? '<span class="badge badge-warning">Pending</span>'
            : '';

    return `
    <div class="scenario-card">
      <div class="scenario-info">
        <span class="scenario-number">#${id}</span>
        <span class="scenario-title">${title}</span>
        ${statusBadge}
      </div>
      <button class="btn btn-primary start-btn" data-scenario-id="${id}">
        ${status === 'completed' ? 'Try Again' : 'Start'}
      </button>
    </div>
  `;
}

function renderUnauthenticatedView(container: HTMLElement): void {
    container.innerHTML = `
    <div class="scenarios-page">
      <div class="card" style="max-width: 400px; margin: 100px auto; text-align: center;">
        <h2>Please Sign In</h2>
        <p>You need to sign in to view the practice scenarios.</p>
        <a href="/" class="btn btn-primary" style="display: inline-block; text-decoration: none;">
          Go to Login
        </a>
      </div>
    </div>
  `;
}
