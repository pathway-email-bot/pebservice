/**
 * Scenarios Page Component
 * 
 * Displays the list of available email practice scenarios.
 * Scenarios are loaded from bundled static files (fetched at build time from service).
 */

import { completeMagicLinkSignIn, onAuthChange, logout, getCurrentUser } from '../auth';
import { listScenarios, sendScenarioEmail, type ScenarioMetadata } from '../scenarios-api';
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
        await renderAuthenticatedView(container, currentUser);
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

async function renderAuthenticatedView(container: HTMLElement, user: User): Promise<void> {
    // Load scenarios from bundled files
    const scenarios = await listScenarios();
    
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
          ${scenarios.map(scenario => renderScenarioCard(scenario)).join('')}
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
        btn.addEventListener('click', async (e) => {
            const scenarioId = (e.target as HTMLElement).dataset.scenarioId;
            if (!scenarioId) return;
            
            const button = e.target as HTMLButtonElement;
            button.disabled = true;
            button.textContent = 'Starting...';
            
            try {
                const result = await sendScenarioEmail(scenarioId);
                if (result.success) {
                    alert(`✅ Scenario started! Check your email for the scenario prompt. (Attempt: ${result.attemptId})`);
                    button.textContent = 'Started';
                    button.classList.add('disabled');
                } else {
                    alert('❌ Failed to start scenario. Please try again.');
                    button.disabled = false;
                    button.textContent = 'Start';
                }
            } catch (error) {
                console.error('Error starting scenario:', error);
                alert(`❌ Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
                button.disabled = false;
                button.textContent = 'Start';
            }
        });
    });
}

function renderScenarioCard(scenario: ScenarioMetadata): string {
    return `
    <div class="scenario-card">
      <div class="scenario-info">
        <h3 class="scenario-title">${scenario.name}</h3>
        <p class="scenario-description">${scenario.description}</p>
        <p class="scenario-role"><strong>Counterpart:</strong> ${scenario.counterpart_role}</p>
      </div>
      <button class="btn btn-primary start-btn" data-scenario-id="${scenario.id}">
        Start
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
