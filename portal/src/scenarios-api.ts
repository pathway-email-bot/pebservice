/**
 * Scenarios API & Cloud Functions Client
 * 
 * Loads scenario metadata from bundled JSON files (single source of truth: service/email_agent/scenarios/)
 * Calls Cloud Functions for scenario management
 */
import { auth } from './firebase-config';

const CLOUD_FUNCTION_BASE_URL = 'https://us-central1-pathway-email-bot-6543.cloudfunctions.net';

export interface ScenarioMetadata {
  id: string;  // Extracted from filename (e.g., "missed_remote_standup")
  name: string;
  interaction_type: 'initiate' | 'reply';  // Who sends email first
  description: string;
  environment: string;
  counterpart_role: string;
  student_task: string;
  counterpart_style: string;
  grading_focus: string;
  starter_sender_name: string;
  starter_subject: string;
  starter_email_body: string | null;
  starter_email_generation_hint: string;
}

export interface StartScenarioRequest {
  email: string;
  scenarioId: string;
}

export interface StartScenarioResponse {
  success: boolean;
  attemptId: string;
  message: string;
}

/**
 * List all available scenarios from bundled static files
 * During build, GitHub Actions copies scenarios from service/email_agent/scenarios/ to public/scenarios/
 */
export async function listScenarios(): Promise<ScenarioMetadata[]> {
  try {
    // Fetch the manifest of scenario files created at build time
    const response = await fetch('./scenarios/manifest.json');

    if (!response.ok) {
      console.warn('Scenarios manifest not found, falling back to empty list');
      return [];
    }

    const manifest = await response.json() as string[];

    // Load each scenario JSON file
    const scenarios = await Promise.all(
      manifest.map(async (filename) => {
        try {
          const scenarioResponse = await fetch(`./scenarios/${filename}`);
          if (!scenarioResponse.ok) {
            console.warn(`Failed to load scenario: ${filename}`);
            return null;
          }
          const data = await scenarioResponse.json();
          // Extract ID from filename (e.g., "missed_remote_standup.json" -> "missed_remote_standup")
          const id = filename.replace('.json', '');
          return { id, ...data } as ScenarioMetadata;
        } catch (error) {
          console.warn(`Error loading scenario ${filename}:`, error);
          return null;
        }
      })
    );

    // Filter out any null values from failed loads
    return scenarios.filter((s): s is ScenarioMetadata => s !== null);
  } catch (error) {
    console.error('Error loading scenarios:', error);
    return [];
  }
}

/**
 * Start a scenario — creates the attempt server-side and
 * sends the starter email for REPLY scenarios.
 */
export async function startScenario(scenarioId: string): Promise<StartScenarioResponse> {
  const user = auth.currentUser;
  if (!user) {
    throw new Error('User not authenticated');
  }

  const token = await user.getIdToken();

  const response = await fetch(`${CLOUD_FUNCTION_BASE_URL}/start_scenario`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      email: user.email,
      scenarioId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.error || 'Failed to start scenario');
  }

  return response.json();
}
