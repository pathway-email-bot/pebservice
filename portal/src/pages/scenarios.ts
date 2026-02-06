/**
 * Scenarios Page Component
 * 
 * Displays the list of available email practice scenarios with drawer-based UX.
 * Scenarios are loaded from bundled static files (fetched at build time from service).
 */

import { completeMagicLinkSignIn, onAuthChange, logout, getCurrentUser } from '../auth';
import { listScenarios, sendScenarioEmail, type ScenarioMetadata } from '../scenarios-api';
import { createAttempt, listenToAttempt, type Attempt } from '../firestore-service';
import type { User } from 'firebase/auth';

// Global state
let currentScenarios: ScenarioMetadata[] = [];
let activeAttemptId: string | null = null;
let activeScenarioId: string | null = null;
let attemptUnsubscribe: (() => void) | null = null;

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
        try {
            await renderAuthenticatedView(container, currentUser);
        } catch (error) {
            console.error('Error rendering authenticated view:', error);
            container.innerHTML = `<div class="message message-error">Error loading scenarios: ${error}</div>`;
        }
    } else {
        renderUnauthenticatedView(container);
    }

    // Listen for auth changes
    onAuthChange((user) => {
        if (user) {
            renderAuthenticatedView(container, user).catch(err => {
                console.error('Error in auth change handler:', err);
            });
        } else {
            renderUnauthenticatedView(container);
        }
    });
}

async function renderAuthenticatedView(container: HTMLElement, user: User): Promise<void> {
    // Load scenarios from bundled files
    try {
        currentScenarios = await listScenarios();
        
        if (!currentScenarios || currentScenarios.length === 0) {
            container.innerHTML = `
                <div class="scenarios-page">
                    <div class="message message-warning">No scenarios found. Please check the build configuration.</div>
                </div>
            `;
            return;
        }
    } catch (error) {
        console.error('Error loading scenarios:', error);
        container.innerHTML = `
            <div class="scenarios-page">
                <div class="message message-error">Failed to load scenarios: ${error}</div>
            </div>
        `;
        return;
    }
    
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
        <p class="instruction">Click "Start" to begin. Only one scenario can be active at a time.</p>
        
        <div class="scenario-list" id="scenario-list">
          ${currentScenarios.map(scenario => renderScenarioCard(scenario, false)).join('')}
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
    attachScenarioHandlers();
}

function attachScenarioHandlers(): void {
    // Start button handlers
    document.querySelectorAll('.start-btn').forEach(btn => {
        btn.addEventListener('click', handleStartScenario);
    });

    // Resend email button handlers
    document.querySelectorAll('.resend-btn').forEach(btn => {
        btn.addEventListener('click', handleResendEmail);
    });
}

async function handleStartScenario(e: Event): Promise<void> {
    const scenarioId = (e.target as HTMLElement).dataset.scenarioId;
    if (!scenarioId) return;
    
    const scenario = currentScenarios.find(s => s.id === scenarioId);
    if (!scenario) return;
    
    const button = e.target as HTMLButtonElement;
    button.disabled = true;
    button.textContent = 'Starting...';
    
    try {
        // 1. Always create Firestore attempt first
        const attemptId = await createAttempt(scenarioId);
        activeAttemptId = attemptId;
        activeScenarioId = scenarioId;
        
        // 2. For REPLY scenarios, also send email via Cloud Function
        if (scenario.interaction_type === 'reply') {
            try {
                await sendScenarioEmail(scenarioId, attemptId);
            } catch (emailError) {
                console.error('Error sending scenario email:', emailError);
                // Don't fail the whole operation - user can retry with "Resend Email" button
                alert(`⚠️ Scenario started but email sending failed. Use the "Resend Email" button to retry.`);
            }
        }
        
        // 3. Expand this scenario card and show instructions
        rerenderScenarios();
        
        // 4. Set up Firestore listener for grading results
        if (attemptUnsubscribe) {
            attemptUnsubscribe();
        }
        attemptUnsubscribe = listenToAttempt(attemptId, (attempt) => {
            if (attempt && attempt.status === 'graded') {
                updateScenarioWithGrading(scenarioId, attempt);
            }
        });
        
    } catch (error) {
        console.error('Error starting scenario:', error);
        alert(`❌ Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
        button.disabled = false;
        button.textContent = 'Start';
    }
}

async function handleResendEmail(e: Event): Promise<void> {
    const scenarioId = (e.target as HTMLElement).dataset.scenarioId;
    if (!scenarioId || !activeAttemptId) return;
    
    const button = e.target as HTMLButtonElement;
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Sending...';
    
    try {
        await sendScenarioEmail(scenarioId, activeAttemptId);
        alert('✅ Email resent! Check your inbox.');
        button.textContent = 'Resent ✓';
        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
        }, 2000);
    } catch (error) {
        console.error('Error resending email:', error);
        alert(`❌ Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
        button.disabled = false;
        button.textContent = originalText;
    }
}

function rerenderScenarios(): void {
    const listContainer = document.getElementById('scenario-list');
    if (!listContainer) return;
    
    listContainer.innerHTML = currentScenarios
        .map(scenario => renderScenarioCard(scenario, scenario.id === activeScenarioId))
        .join('');
    
    // Reattach event handlers
    attachScenarioHandlers();
}

function updateScenarioWithGrading(scenarioId: string, attempt: Attempt): void {
    const card = document.querySelector(`.scenario-card[data-scenario-id="${scenarioId}"]`);
    if (!card) return;
    
    const drawer = card.querySelector('.scenario-drawer');
    if (!drawer) return;
    
    // Find or create grading section
    let gradingSection = drawer.querySelector('.grading-results');
    if (!gradingSection) {
        gradingSection = document.createElement('div');
        gradingSection.className = 'grading-results';
        drawer.appendChild(gradingSection);
    }
    
    gradingSection.innerHTML = `
        <div class="grading-header">
            <h4>📊 Results</h4>
            <div class="score">Score: ${attempt.score}/${attempt.maxScore}</div>
        </div>
        <div class="feedback">
            <p><strong>Feedback:</strong></p>
            <p>${attempt.feedback}</p>
        </div>
        <div class="graded-time">
            Graded at: ${attempt.gradedAt?.toLocaleString() || 'Unknown'}
        </div>
    `;
}

function renderScenarioCard(scenario: ScenarioMetadata, isExpanded: boolean): string {
    const isActive = isExpanded;
    
    return `
    <div class="scenario-card ${isActive ? 'active' : ''}" data-scenario-id="${scenario.id}">
      <div class="scenario-header">
        <div class="scenario-info">
          <h3 class="scenario-title">${scenario.name}</h3>
          <p class="scenario-description">${scenario.description}</p>
          <p class="scenario-role"><strong>Counterpart:</strong> ${scenario.counterpart_role}</p>
        </div>
        ${!isActive ? `
          <button class="btn btn-primary start-btn" data-scenario-id="${scenario.id}">
            Start
          </button>
        ` : ''}
      </div>
      
      ${isActive ? `
        <div class="scenario-drawer">
          <div class="task-section">
            <h4>📝 Your Task</h4>
            <p>${scenario.student_task}</p>
          </div>
          
          <div class="instructions-section">
            <h4>📬 Instructions</h4>
            ${scenario.interaction_type === 'initiate' ? `
              <p><strong>Send an email to:</strong> <code>pathwayemailbot@gmail.com</code></p>
              <p>Compose and send your email from your email client. You'll receive feedback automatically.</p>
            ` : `
              <p><strong>Check your email inbox</strong> for a message from the bot.</p>
              <p>Reply to that email with your response. You'll receive feedback automatically.</p>
              <button class="btn btn-secondary resend-btn" data-scenario-id="${scenario.id}">
                📧 Resend Email
              </button>
            `}
          </div>
          
          <div class="status-section">
            <p class="pending-status">⏳ Waiting for your email...</p>
          </div>
        </div>
      ` : ''}
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
