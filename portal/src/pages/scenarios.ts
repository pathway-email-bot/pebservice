/**
 * Scenarios Page Component
 * 
 * Displays the list of available email practice scenarios with drawer-based UX.
 * Scenarios are loaded from bundled static files (fetched at build time from service).
 * Attempt history is loaded from Firestore to show score badges and restore active state.
 */

import { logout, getCurrentUser } from '../auth';
import { listScenarios, startScenario, type ScenarioMetadata } from '../scenarios-api';
import { listenToAttempt, listenToAttempts, listenToUserData, setFirstName, type Attempt } from '../firestore-service';
import type { User } from 'firebase/auth';
import { escapeHtml } from '../utils';
import { devmode } from '../devmode';

// Global state
let currentScenarios: ScenarioMetadata[] = [];
let expandedScenarioId: string | null = null;   // which drawer is open (read-only preview)
let activeScenarioId: string | null = null;      // which has a live pending attempt

let attemptUnsubscribe: (() => void) | null = null;
let attemptsUnsubscribe: (() => void) | null = null;
let userDataUnsubscribe: (() => void) | null = null;
let studentFirstName: string | null = null;

// Attempts grouped by scenario: scenarioId -> Attempt[] (sorted newest first)
let attemptsByScenario: Map<string, Attempt[]> = new Map();

// Stale attempt threshold: 1 hour
const STALE_ATTEMPT_MS = 60 * 60 * 1000;

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
        <div class="user-info" id="user-info">
          ${renderUserHeader(user)}
        </div>
      </header>
      
      <main class="scenarios-container">
        <p class="subtitle">Choose a scenario to practice your professional email skills</p>
        <p class="instruction">Click a scenario to learn more. Press "Start" inside the drawer when you're ready to begin.</p>
        
        <div class="scenario-list" id="scenario-list">
          ${currentScenarios.map(scenario => renderScenarioCard(scenario, false, false)).join('')}
        </div>
      </main>
    </div>
  `;

  // Add header handlers (logout + edit name)
  attachHeaderHandlers();

  // Add start button handlers
  attachScenarioHandlers();

  // Load attempt history from Firestore and restore active state
  loadAttemptHistory();

  // Listen to user data for firstName (piggybacks on existing user doc)
  if (userDataUnsubscribe) userDataUnsubscribe();
  userDataUnsubscribe = listenToUserData((data) => {
    const newName = data?.firstName || null;
    if (newName !== studentFirstName) {
      studentFirstName = newName;
      const userInfo = document.getElementById('user-info');
      if (userInfo) {
        userInfo.innerHTML = renderUserHeader(user);
        attachHeaderHandlers();
      }
    }
    // Show name modal if no name is set
    if (!studentFirstName) {
      showNameModal(user);
    }
  });

  // Dev preview mode: ?devmode=preview auto-activates first scenario
  // so you can see active state styling without calling Cloud Function
  if (devmode.has('preview')) {
    activeScenarioId = currentScenarios[0]?.id ?? null;
    expandedScenarioId = activeScenarioId;
    rerenderScenarios();

    // Named sub-flags for specific preview behaviors
    if (devmode.has('score_arrives')) {
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
 * Auto-expires stale pending attempts older than 24 hours.
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
      const ageMs = Date.now() - pendingAttempt.startedAt.getTime();
      if (ageMs < STALE_ATTEMPT_MS) {
        // Recent attempt — restore as active
        activeScenarioId = pendingAttempt.scenarioId;
        expandedScenarioId = pendingAttempt.scenarioId;

        // Re-attach listener for this specific attempt
        if (attemptUnsubscribe) attemptUnsubscribe();
        attemptUnsubscribe = listenToAttempt(pendingAttempt.id, (attempt) => {
          if (attempt && attempt.status === 'graded') {
            updateScenarioWithGrading(pendingAttempt.scenarioId, attempt);
          }
        });
      } else {
        console.info(`[UX] Stale pending attempt for "${pendingAttempt.scenarioId}" (${Math.round(ageMs / 3600000)}h old) — not restoring as active`);
      }
    }

    // Re-render to show score badges and restore active state
    rerenderScenarios();
  });
}

function renderUserHeader(user: User): string {
  if (studentFirstName) {
    return `
      <span>Hi <strong>${escapeHtml(studentFirstName)}</strong></span>
      <a href="#" id="edit-name-link" class="edit-name-link">Edit Name</a>
      <button id="logout-btn" class="btn btn-secondary">Sign Out</button>
    `;
  }
  return `
    <span>${user.email}</span>
    <button id="logout-btn" class="btn btn-secondary">Sign Out</button>
  `;
}

function attachHeaderHandlers(): void {
  document.getElementById('logout-btn')?.addEventListener('click', async () => {
    if (attemptUnsubscribe) attemptUnsubscribe();
    if (attemptsUnsubscribe) attemptsUnsubscribe();
    if (userDataUnsubscribe) userDataUnsubscribe();
    await logout();
  });

  document.getElementById('edit-name-link')?.addEventListener('click', (e) => {
    e.preventDefault();
    handleEditName();
  });
}

function showNameModal(user: User): void {
  const overlay = document.createElement('div');
  overlay.className = 'name-modal-overlay';
  overlay.innerHTML = `
    <div class="name-modal">
      <div class="welcome-icon">👋</div>
      <h2>Welcome! What's your first name?</h2>
      <p class="subtitle">We'll use it to personalize your practice emails.</p>
      <form id="name-form">
        <div class="form-group">
          <input
            type="text"
            id="first-name-input"
            placeholder="e.g. Sarah"
            required
            maxlength="30"
            autocomplete="given-name"
          />
        </div>
        <button type="submit" class="btn btn-primary" id="name-submit-btn">Begin Practice</button>
      </form>
    </div>
  `;

  document.body.appendChild(overlay);

  // Focus the input
  const input = document.getElementById('first-name-input') as HTMLInputElement;
  input?.focus();

  const form = document.getElementById('name-form') as HTMLFormElement;
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = input.value.trim();
    if (!name) return;

    const btn = document.getElementById('name-submit-btn') as HTMLButtonElement;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Saving…';

    try {
      await setFirstName(name);
      studentFirstName = name;

      // Update header and remove modal
      const userInfo = document.getElementById('user-info');
      if (userInfo) userInfo.innerHTML = renderUserHeader(user);
      attachHeaderHandlers();
      overlay.remove();
    } catch (error) {
      console.error('Error saving name:', error);
      btn.disabled = false;
      btn.textContent = 'Begin Practice';
    }
  });
}

function handleEditName(): void {
  const userInfo = document.getElementById('user-info');
  if (!userInfo) return;

  const currentName = escapeHtml(studentFirstName || '');
  userInfo.innerHTML = `
    <form id="edit-name-form" class="edit-name-form">
      <input
        type="text"
        id="edit-name-input"
        value="${currentName}"
        maxlength="30"
        autocomplete="given-name"
      />
      <button type="submit" class="btn btn-primary btn-sm">Save</button>
      <button type="button" class="btn btn-secondary btn-sm" id="cancel-edit-name">Cancel</button>
    </form>
  `;

  const input = document.getElementById('edit-name-input') as HTMLInputElement;
  input?.focus();
  input?.select();

  const user = getCurrentUser();

  document.getElementById('cancel-edit-name')?.addEventListener('click', () => {
    if (userInfo && user) {
      userInfo.innerHTML = renderUserHeader(user);
      attachHeaderHandlers();
    }
  });

  document.getElementById('edit-name-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = input.value.trim();
    if (!name) return;

    try {
      await setFirstName(name);
      studentFirstName = name;
      if (userInfo && user) {
        userInfo.innerHTML = renderUserHeader(user);
        attachHeaderHandlers();
      }
    } catch (error) {
      console.error('Error updating name:', error);
    }
  });
}

function attachScenarioHandlers(): void {
  // Clickable card headers toggle the drawer
  document.querySelectorAll('.scenario-header-clickable').forEach(header => {
    header.addEventListener('click', handleToggleDrawer);
  });

  // Start button handlers (now inside the drawer)
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

function handleToggleDrawer(e: Event): void {
  // Don't toggle if clicking a button or link inside the header
  const target = e.target as HTMLElement;
  if (target.closest('button') || target.closest('a')) return;

  const header = (e.currentTarget as HTMLElement);
  const scenarioId = header.dataset.scenarioId;
  if (!scenarioId) return;

  // Toggle: if already expanded, collapse; otherwise expand this one
  if (expandedScenarioId === scenarioId) {
    expandedScenarioId = null;
  } else {
    expandedScenarioId = scenarioId;
  }
  rerenderScenarios();
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
  const button = e.target as HTMLElement;
  const scenarioId = button.dataset.scenarioId;
  if (!scenarioId) return;

  const scenario = currentScenarios.find(s => s.id === scenarioId);
  if (!scenario) return;

  // Drawer is already open (Start button is inside it) — disable button + show spinner
  activeScenarioId = scenarioId;

  const startBtn = document.querySelector(`.scenario-card[data-scenario-id="${scenarioId}"] .start-btn`) as HTMLButtonElement | null;
  if (startBtn) {
    startBtn.disabled = true;
    startBtn.innerHTML = '<span class="spinner"></span> Setting active scenario…';
  }

  const drawer = document.querySelector(`.scenario-card[data-scenario-id="${scenarioId}"] .scenario-drawer`);
  // Update header to show active styling
  const card = document.querySelector(`.scenario-card[data-scenario-id="${scenarioId}"]`);
  card?.classList.add('active');

  try {
    // Call start_scenario Cloud Function (creates attempt + sends email for REPLY)
    const result = await startScenario(scenarioId);

    // Cloud Function returned — swap drawer content to active state
    if (drawer) {
      drawer.innerHTML = renderDrawerActive(scenario);
      // Re-attach copy-email handler
      drawer.querySelector('.copy-email-btn')?.addEventListener('click', handleCopyEmail);
    }

    // Set up grading listener
    if (devmode.active && result.attemptId.startsWith('mock-')) {
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

    // Reset active state but keep drawer open
    activeScenarioId = null;
    rerenderScenarios();

    // Show error on the card
    const errorCard = document.querySelector(`.scenario-card[data-scenario-id="${scenarioId}"]`);
    const errorDiv = errorCard?.querySelector('.error-message') as HTMLElement;
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
    .map(scenario => renderScenarioCard(
      scenario,
      scenario.id === expandedScenarioId,
      scenario.id === activeScenarioId
    ))
    .join('');

  // Toggle dim styling on inactive cards when one is active
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
            ${a.feedback ? `
              <div class="attempt-feedback">
                <p>${a.feedback}</p>
              </div>
            ` : ''}
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



/** Active attempt drawer content (after Cloud Function returns) */
function renderDrawerActive(scenario: ScenarioMetadata): string {
  return `
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
        <p class="pending-status">🤗 We are waiting for your email! Compose your best email and send it to pathwayemailbot@gmail.com 💛</p>
      </div>
    </div>
  `;
}

/** Render the drawer preview (read-only, before starting) */
function renderDrawerPreview(scenario: ScenarioMetadata): string {
  const attempts = attemptsByScenario.get(scenario.id);
  const latestGraded = attempts?.find(a => a.status === 'graded');

  // Previous grading results shown on load
  let gradingHtml = '';
  if (latestGraded) {
    gradingHtml = `
      <div class="grading-results">
        <div class="grading-header">
          <h4>📊 Latest Result</h4>
          <div class="score">Score: ${latestGraded.score}/${latestGraded.maxScore}</div>
        </div>
        <div class="feedback">
          <p><strong>Feedback:</strong></p>
          <p>${latestGraded.feedback || 'No feedback available'}</p>
        </div>
        <div class="graded-time">
          Graded at: ${latestGraded.gradedAt?.toLocaleString() || 'Unknown'}
        </div>
      </div>
    `;
  }

  return `
    <div class="drawer-content-loaded">
      <div class="task-section">
        <h4>📝 Your Task</h4>
        <p>${scenario.student_task}</p>
      </div>

      <div class="drawer-actions">
        <div class="error-message" style="display: none;"></div>
        <button class="btn btn-primary start-btn" data-scenario-id="${scenario.id}">
          ${scenario.interaction_type === 'initiate' ? '📤 Start — You Send First' : '📥 Start — You\'ll Receive an Email'}
        </button>
      </div>

      ${gradingHtml}
    </div>
  `;
}

function renderScenarioCard(scenario: ScenarioMetadata, isExpanded: boolean, isActive: boolean): string {
  const scoreIndicator = getScoreIndicator(scenario.id);
  const interactionBadge = scenario.interaction_type === 'initiate'
    ? '<span class="interaction-badge badge-initiate" title="You compose and send the first email">📤 You Send</span>'
    : '<span class="interaction-badge badge-reply" title="You reply to an email from the bot">📥 You Reply</span>';

  // Build the score column for the card header
  let headerScoreHtml = scoreIndicator;
  if (isActive && !scoreIndicator) {
    headerScoreHtml = `
      <div class="score-indicator-row">
        <span class="score-badge">Score pending<span class="dots"></span></span>
      </div>
    `;
  } else if (isActive) {
    headerScoreHtml = `
      <div class="score-indicator-row">
        <span class="score-badge">Score pending<span class="dots"></span></span>
      </div>
    `;
  }

  // Build previous attempts link
  const prevAttemptsLink = (() => {
    const atts = attemptsByScenario.get(scenario.id);
    if (!atts) return '';
    const gradedCount = atts.filter(a => a.status === 'graded').length;
    if (gradedCount === 0) return '';
    return `<a href="#" class="prev-attempts-link" data-scenario-id="${scenario.id}">(${gradedCount} previous)</a>`;
  })();

  // Determine drawer content
  let drawerHtml = '';
  if (isExpanded) {
    if (isActive) {
      drawerHtml = renderDrawerActive(scenario);
    } else {
      drawerHtml = renderDrawerPreview(scenario);
    }
  }

  const expandIcon = isExpanded ? '▾' : '▸';

  return `
    <div class="scenario-card ${isActive ? 'active' : ''} ${isExpanded ? 'expanded' : ''}" data-scenario-id="${scenario.id}">
      <div class="scenario-header scenario-header-clickable" data-scenario-id="${scenario.id}">
        <div class="scenario-info">
          <h3 class="scenario-title">
            <span class="expand-icon">${expandIcon}</span>
            ${scenario.name}
            ${interactionBadge}
            ${isActive ? '<span class="active-badge">🟢 Active Scenario</span>' : ''}
          </h3>
          <p class="scenario-description">${scenario.description}</p>
          <p class="scenario-role"><strong>Counterpart:</strong> ${scenario.counterpart_role}</p>
        </div>
        <div class="scenario-actions">
          ${headerScoreHtml}
          ${prevAttemptsLink}
        </div>
      </div>
      
      ${isExpanded ? `
        <div class="scenario-drawer">
          ${drawerHtml}
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
