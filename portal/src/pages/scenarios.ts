/**
 * Scenarios Page Component
 * 
 * Displays the list of available email practice scenarios with drawer-based UX.
 * Scenarios are loaded from bundled static files (fetched at build time from service).
 */

import { logout, getCurrentUser } from '../auth';
import { listScenarios, startScenario, type ScenarioMetadata } from '../scenarios-api';
import { listenToAttempt, type Attempt } from '../firestore-service';
import type { User } from 'firebase/auth';

// Global state
let currentScenarios: ScenarioMetadata[] = [];
let activeScenarioId: string | null = null;
let attemptUnsubscribe: (() => void) | null = null;

export async function renderScenariosPage(container: HTMLElement): Promise<void> {
  // main.ts handles auth routing — if we're here, user should be logged in
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
    // Auth listener in main.ts will automatically show login page
  });

  // Add start button handlers
  attachScenarioHandlers();
}

function attachScenarioHandlers(): void {
  // Start button handlers
  document.querySelectorAll('.start-btn').forEach(btn => {
    btn.addEventListener('click', handleStartScenario);
  });
}

async function handleStartScenario(e: Event): Promise<void> {
  const scenarioId = (e.target as HTMLElement).dataset.scenarioId;
  if (!scenarioId) return;

  const scenario = currentScenarios.find(s => s.id === scenarioId);
  if (!scenario) return;

  const button = e.target as HTMLButtonElement;
  const card = button.closest('.scenario-card');
  const errorDiv = card?.querySelector('.error-message') as HTMLElement;

  // Clear any previous errors
  if (errorDiv) {
    errorDiv.style.display = 'none';
  }

  button.disabled = true;
  button.innerHTML = '⏳ Starting...';

  try {
    // Call start_scenario Cloud Function (creates attempt + sends email for REPLY)
    const result = await startScenario(scenarioId);
    activeScenarioId = scenarioId;

    // Expand this scenario card and show instructions
    rerenderScenarios();

    // Set up Firestore listener for grading results
    if (attemptUnsubscribe) {
      attemptUnsubscribe();
    }
    attemptUnsubscribe = listenToAttempt(result.attemptId, (attempt) => {
      if (attempt && attempt.status === 'graded') {
        updateScenarioWithGrading(scenarioId, attempt);
      }
    });

  } catch (error) {
    console.error('Error starting scenario:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';

    if (errorDiv) {
      errorDiv.textContent = `❌ Error: ${errorMessage}`;
      errorDiv.style.display = 'block';
    }

    button.disabled = false;
    button.textContent = 'Start';
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
          <div class="scenario-actions">
            <div class="error-message" style="display: none;"></div>
            <button class="btn btn-primary start-btn" data-scenario-id="${scenario.id}">
              Start
            </button>
          </div>
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
