/**
 * Scenarios Page Component
 * 
 * Displays the list of available email practice scenarios with drawer-based UX.
 * Scenarios are loaded from bundled static files (fetched at build time from service).
 * Attempt history is loaded from Firestore to show score badges and restore active state.
 */

import { logout, getCurrentUser } from '../auth';
import { listScenarios, startScenario, type ScenarioMetadata } from '../scenarios-api';
import { listenToAttempt, listenToAttempts, type Attempt } from '../firestore-service';
import type { User } from 'firebase/auth';

// Global state
let currentScenarios: ScenarioMetadata[] = [];
let activeScenarioId: string | null = null;
let isDrawerLoading = false;
let attemptUnsubscribe: (() => void) | null = null;
let attemptsUnsubscribe: (() => void) | null = null;

// Attempts grouped by scenario: scenarioId -> Attempt[] (sorted newest first)
let attemptsByScenario: Map<string, Attempt[]> = new Map();

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
    // Clean up listeners before logout
    if (attemptUnsubscribe) attemptUnsubscribe();
    if (attemptsUnsubscribe) attemptsUnsubscribe();
    await logout();
  });

  // Add start button handlers
  attachScenarioHandlers();

  // Load attempt history from Firestore and restore active state
  loadAttemptHistory();

  // Dev preview mode: ?preview in URL auto-activates first scenario
  // so you can see active state styling locally without calling Cloud Function
  // Gated behind import.meta.env.DEV — Vite strips this from production builds
  if (import.meta.env.DEV && new URLSearchParams(window.location.search).has('preview')) {
    const previewMode = new URLSearchParams(window.location.search).get('preview') || 'default';
    activeScenarioId = currentScenarios[0]?.id ?? null;
    rerenderScenarios();
    console.info(`[DEV] Preview mode: "${previewMode}"`);

    // Named preview modes
    if (previewMode === 'score_arrives') {
      setTimeout(() => {
        const badge = document.querySelector('.score-badge');
        if (badge) {
          badge.classList.add('scored');
          badge.innerHTML = '⭐ Score: 22/25 — Great work!';
        }
      }, 3000);
    }
  }
}

/**
 * Load all attempts from Firestore, group by scenario, and restore active state.
 * Sets up a real-time listener so score badges update live.
 */
function loadAttemptHistory(): void {
  if (attemptsUnsubscribe) attemptsUnsubscribe();

  attemptsUnsubscribe = listenToAttempts((attempts) => {
    // Group attempts by scenario
    attemptsByScenario = new Map();
    for (const attempt of attempts) {
      const existing = attemptsByScenario.get(attempt.scenarioId) || [];
      existing.push(attempt);
      attemptsByScenario.set(attempt.scenarioId, existing);
    }

    // Check for any active (pending) attempt and restore state
    const pendingAttempt = attempts.find(a => a.status === 'pending');
    if (pendingAttempt && !activeScenarioId) {
      activeScenarioId = pendingAttempt.scenarioId;


      // Re-attach listener for this specific attempt
      if (attemptUnsubscribe) attemptUnsubscribe();
      attemptUnsubscribe = listenToAttempt(pendingAttempt.id, (attempt) => {
        if (attempt && attempt.status === 'graded') {
          updateScenarioWithGrading(pendingAttempt.scenarioId, attempt);
        }
      });
    }

    // Re-render to show score badges and restore active state
    rerenderScenarios();
  });
}

function attachScenarioHandlers(): void {
  // Start button handlers
  document.querySelectorAll('.start-btn').forEach(btn => {
    btn.addEventListener('click', handleStartScenario);
  });

  // Copy email button handlers
  document.querySelectorAll('.copy-email-btn').forEach(btn => {
    btn.addEventListener('click', handleCopyEmail);
  });

  // Previous attempts link handlers
  document.querySelectorAll('.prev-attempts-link').forEach(link => {
    link.addEventListener('click', handleShowPreviousAttempts);
  });
}

async function handleCopyEmail(e: Event): Promise<void> {
  const button = e.target as HTMLButtonElement;
  const email = button.dataset.email;
  if (!email) return;

  try {
    await navigator.clipboard.writeText(email);
    button.classList.add('copied');
    button.textContent = '✅ Copied!';
    setTimeout(() => {
      button.classList.remove('copied');
      button.textContent = '📋 Copy';
    }, 1500);
  } catch (err) {
    console.warn('Clipboard copy failed:', err);
    // Fallback: select the text in the code element
    const codeEl = button.closest('.copy-email-row')?.querySelector('code');
    if (codeEl) {
      const range = document.createRange();
      range.selectNodeContents(codeEl);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(range);
    }
  }
}

async function handleStartScenario(e: Event): Promise<void> {
  const scenarioId = (e.target as HTMLElement).dataset.scenarioId;
  if (!scenarioId) return;

  const scenario = currentScenarios.find(s => s.id === scenarioId);
  if (!scenario) return;

  // Immediately open drawer in loading state
  activeScenarioId = scenarioId;
  isDrawerLoading = true;
  const scrollY = window.scrollY; // save scroll position before DOM rebuild
  rerenderScenarios();
  window.scrollTo(0, scrollY); // restore — prevents any jump

  try {
    // Call start_scenario Cloud Function (creates attempt + sends email for REPLY)
    const result = await startScenario(scenarioId);

    // Loading done — swap drawer content in-place (avoids re-triggering expand animation)
    isDrawerLoading = false;
    const drawer = document.querySelector('.scenario-drawer');
    if (drawer) {
      drawer.innerHTML = `
        <div class="drawer-content-loaded">
          <div class="task-section">
            <h4>📝 Your Task</h4>
            <p>${scenario.student_task}</p>
          </div>
          
          <div class="instructions-section">
            <h4>📬 Instructions</h4>
            ${scenario.interaction_type === 'initiate' ? `
              <div class="copy-email-row">
                <p style="margin-bottom:0"><strong>Send an email to:</strong> <code>pathwayemailbot@gmail.com</code></p>
                <button class="copy-email-btn" data-email="pathwayemailbot@gmail.com" type="button">📋 Copy</button>
              </div>
              <p>Compose and send your email from your email client. You'll receive feedback automatically.</p>
            ` : `
              <p><strong>Check your email inbox</strong> for a message from the bot.</p>
              <p>Reply to that email with your response. You'll receive feedback automatically.</p>
            `}
          </div>
          
          <div class="status-section">
            <p class="pending-status">🤗 You're all set! Compose your best email and send it to pathwayemailbot@gmail.com — we'll be here when it arrives 💛</p>
          </div>
        </div>
      `;
      // Re-attach copy-email handler
      drawer.querySelector('.copy-email-btn')?.addEventListener('click', handleCopyEmail);
    }

    // Set up grading listener
    if (import.meta.env.DEV && result.attemptId.startsWith('mock-')) {
      // DEV mock: simulate grading after 3 seconds
      console.info('[DEV MOCK] Simulating grading in 3 seconds...');
      setTimeout(() => {
        updateScenarioWithGrading(scenarioId, {
          id: result.attemptId,
          scenarioId,
          status: 'graded',
          startedAt: new Date(),
          score: 22,
          maxScore: 25,
          feedback: '[DEV MOCK] Great email! Clear subject line, professional tone, and well-structured content.',
          gradedAt: new Date(),
        });
      }, 3000);
    } else {
      // Production: Firestore listener for real grading results
      if (attemptUnsubscribe) {
        attemptUnsubscribe();
      }
      attemptUnsubscribe = listenToAttempt(result.attemptId, (attempt) => {
        if (attempt && attempt.status === 'graded') {
          updateScenarioWithGrading(scenarioId, attempt);
        }
      });
    }

  } catch (error) {
    console.error('Error starting scenario:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';

    // Collapse drawer back and show error
    activeScenarioId = null;
    isDrawerLoading = false;
    rerenderScenarios();

    // Show error on the card
    const card = document.querySelector(`.scenario-card[data-scenario-id="${scenarioId}"]`);
    const errorDiv = card?.querySelector('.error-message') as HTMLElement;
    if (errorDiv) {
      errorDiv.textContent = `❌ Error: ${errorMessage}`;
      errorDiv.style.display = 'block';
    }
  }
}

function rerenderScenarios(): void {
  const listContainer = document.getElementById('scenario-list');
  if (!listContainer) return;

  listContainer.innerHTML = currentScenarios
    .map(scenario => renderScenarioCard(scenario, scenario.id === activeScenarioId))
    .join('');

  // Toggle dim styling on inactive cards
  if (activeScenarioId) {
    listContainer.classList.add('has-active');
  } else {
    listContainer.classList.remove('has-active');
  }

  // Reattach event handlers
  attachScenarioHandlers();
}

function updateScenarioWithGrading(scenarioId: string, attempt: Attempt): void {
  const card = document.querySelector(`.scenario-card[data-scenario-id="${scenarioId}"]`);
  if (!card) return;

  const drawer = card.querySelector('.scenario-drawer');
  if (!drawer) return;

  // Update score badge with real score
  const badge = card.querySelector('.score-badge');
  if (badge) {
    badge.classList.add('scored');
    badge.innerHTML = `⭐ Score: ${attempt.score}/${attempt.maxScore}`;
  }

  // Update status message
  const pendingStatus = drawer.querySelector('.pending-status');
  if (pendingStatus) {
    pendingStatus.className = 'success-status';
    pendingStatus.textContent = '✅ Your email has been graded!';
  }

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

/**
 * Get score indicator for a scenario based on latest attempt
 */
function getScoreIndicator(scenarioId: string): string {
  const attempts = attemptsByScenario.get(scenarioId);
  if (!attempts || attempts.length === 0) return '';

  // Find latest graded attempt
  const latestGraded = attempts.find(a => a.status === 'graded');
  if (!latestGraded) {
    // Has attempts but none graded — show pending indicator
    const pending = attempts.find(a => a.status === 'pending');
    if (pending) return '<span class="score-indicator pending" title="In progress">⏳</span>';
    return '';
  }

  const score = latestGraded.score ?? 0;
  const maxScore = latestGraded.maxScore ?? 25;
  let colorClass: string;
  if (score >= 20) colorClass = 'green';
  else if (score >= 12) colorClass = 'yellow';
  else colorClass = 'red';

  const attemptCount = attempts.filter(a => a.status === 'graded').length;
  const prevLink = attemptCount > 1
    ? `<a href="#" class="prev-attempts-link" data-scenario-id="${scenarioId}">(${attemptCount - 1} previous)</a>`
    : '';

  return `
    <div class="score-indicator-row">
      <span class="score-indicator ${colorClass}" title="${score}/${maxScore}">
        ${score}/${maxScore}
      </span>
      ${prevLink}
    </div>
  `;
}

function handleShowPreviousAttempts(e: Event): void {
  e.preventDefault();
  const scenarioId = (e.target as HTMLElement).dataset.scenarioId;
  if (!scenarioId) return;

  const attempts = attemptsByScenario.get(scenarioId);
  if (!attempts) return;

  const gradedAttempts = attempts.filter(a => a.status === 'graded');
  const scenario = currentScenarios.find(s => s.id === scenarioId);

  // Build modal
  const modal = document.createElement('div');
  modal.className = 'attempts-modal-overlay';
  modal.innerHTML = `
    <div class="attempts-modal">
      <div class="attempts-modal-header">
        <h3>📊 Previous Attempts — ${scenario?.name || scenarioId}</h3>
        <button class="attempts-modal-close">&times;</button>
      </div>
      <div class="attempts-modal-body">
        ${gradedAttempts.map((a, i) => {
    const score = a.score ?? 0;
    const maxScore = a.maxScore ?? 25;
    let colorClass: string;
    if (score >= 20) colorClass = 'green';
    else if (score >= 12) colorClass = 'yellow';
    else colorClass = 'red';

    return `
            <div class="attempt-row">
              <div class="attempt-info">
                <span class="attempt-number">#${gradedAttempts.length - i}</span>
                <span class="attempt-date">${a.gradedAt?.toLocaleDateString() || 'Unknown'}</span>
              </div>
              <span class="score-indicator ${colorClass}">${score}/${maxScore}</span>
            </div>
          `;
  }).join('')}
      </div>
    </div>
  `;

  // Close handlers
  modal.querySelector('.attempts-modal-close')?.addEventListener('click', () => modal.remove());
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.remove();
  });

  document.body.appendChild(modal);
}

function renderScenarioCard(scenario: ScenarioMetadata, isExpanded: boolean): string {
  const isActive = isExpanded;
  const scoreIndicator = getScoreIndicator(scenario.id);

  // Build the score column for the card header (works for both active and inactive)
  let headerScoreHtml = scoreIndicator; // default: graded score badges for inactive
  if (isActive && !scoreIndicator) {
    // Active with no prior graded score — show pending
    headerScoreHtml = `
      <div class="score-indicator-row">
        <span class="score-badge">Score pending<span class="dots"></span></span>
      </div>
    `;
  } else if (isActive && scoreIndicator) {
    // Active with prior scores — show score + pending note  
    headerScoreHtml = `
      <div class="score-indicator-row">
        <span class="score-badge">Score pending<span class="dots"></span></span>
      </div>
    `;
  }

  // Build previous attempts link for active cards
  const prevAttemptsLink = (() => {
    const atts = attemptsByScenario.get(scenario.id);
    if (!atts) return '';
    const gradedCount = atts.filter(a => a.status === 'graded').length;
    if (gradedCount === 0) return '';
    return `<a href="#" class="prev-attempts-link" data-scenario-id="${scenario.id}">(${gradedCount} previous)</a>`;
  })();

  return `
    <div class="scenario-card ${isActive ? 'active' : ''}" data-scenario-id="${scenario.id}">
      <div class="scenario-header">
        <div class="scenario-info">
          <h3 class="scenario-title">${scenario.name}</h3>
          <p class="scenario-description">${scenario.description}</p>
          <p class="scenario-role"><strong>Counterpart:</strong> ${scenario.counterpart_role}</p>
        </div>
        ${!isActive ? `
          ${scoreIndicator}
          <div class="scenario-actions">
            <div class="error-message" style="display: none;"></div>
            <button class="btn btn-primary start-btn" data-scenario-id="${scenario.id}">
              Start
            </button>
          </div>
        ` : `
          <div class="score-indicator-row">
            ${headerScoreHtml}
            ${prevAttemptsLink}
          </div>
        `}
      </div>
      
      ${isActive ? `
        <div class="scenario-drawer">
          ${isDrawerLoading ? `
            <div class="shimmer-block" style="height: 1.2em; width: 40%; margin-bottom: 12px;"></div>
            <div class="shimmer-block" style="height: 3em; width: 100%; margin-bottom: 16px;"></div>
            <div class="shimmer-block" style="height: 1.2em; width: 50%; margin-bottom: 12px;"></div>
            <div class="shimmer-block" style="height: 4em; width: 100%; margin-bottom: 16px;"></div>
            <div class="shimmer-block" style="height: 2em; width: 70%;"></div>
          ` : `
            <div class="drawer-content-loaded">
              <div class="task-section">
                <h4>📝 Your Task</h4>
                <p>${scenario.student_task}</p>
              </div>
              
              <div class="instructions-section">
                <h4>📬 Instructions</h4>
                ${scenario.interaction_type === 'initiate' ? `
                  <div class="copy-email-row">
                    <p style="margin-bottom:0"><strong>Send an email to:</strong> <code>pathwayemailbot@gmail.com</code></p>
                    <button class="copy-email-btn" data-email="pathwayemailbot@gmail.com" type="button">📋 Copy</button>
                  </div>
                  <p>Compose and send your email from your email client. You'll receive feedback automatically.</p>
                ` : `
                  <p><strong>Check your email inbox</strong> for a message from the bot.</p>
                  <p>Reply to that email with your response. You'll receive feedback automatically.</p>
                `}
              </div>
              
              <div class="status-section">
                <p class="pending-status">🤗 You're all set! Compose your best email and send it to pathwayemailbot@gmail.com — we'll be here when it arrives 💛</p>
              </div>
            </div>
          `}
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
