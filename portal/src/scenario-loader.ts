/**
 * Load scenarios from bundled JSON files
 */

// Import all scenario JSON files
import missedRemoteStandup from './scenarios/missed_remote_standup.json';
import clarifyMultistepProcess from './scenarios/clarify_multistep_process.json';
import clarifyVagueTaskAdmin from './scenarios/clarify_vague_task_admin.json';
import correctErrorInReport from './scenarios/correct_error_in_report.json';
import followUpLateInvoiceVa from './scenarios/follow_up_late_invoice_va.json';
import followUpMissingDocuments from './scenarios/follow_up_missing_documents.json';
import requestDeadlineAdjustment from './scenarios/request_deadline_adjustment_data_entry.json';
import rescheduleClientCall from './scenarios/reschedule_client_call_internet_issue.json';
import rescheduleInternalMeeting from './scenarios/reschedule_internal_meeting_conflict.json';
import respondToCustomerComplaint from './scenarios/respond_to_customer_complaint_support.json';
import respondToFeedback from './scenarios/respond_to_feedback_slow_responses.json';

export interface Scenario {
    name: string;
    description: string;
    counterpart_role: string;
    student_task: string;
    grading_focus: string[];
    starter_sender_name?: string;
    starter_email_body?: string;
}

const scenarioMap: Record<string, Scenario> = {
    'missed_remote_standup': missedRemoteStandup as Scenario,
    'clarify_multistep_process': clarifyMultistepProcess as Scenario,
    'clarify_vague_task_admin': clarifyVagueTaskAdmin as Scenario,
    'correct_error_in_report': correctErrorInReport as Scenario,
    'follow_up_late_invoice_va': followUpLateInvoiceVa as Scenario,
    'follow_up_missing_documents': followUpMissingDocuments as Scenario,
    'request_deadline_adjustment_data_entry': requestDeadlineAdjustment as Scenario,
    'reschedule_client_call_internet_issue': rescheduleClientCall as Scenario,
    'reschedule_internal_meeting_conflict': rescheduleInternalMeeting as Scenario,
    'respond_to_customer_complaint_support': respondToCustomerComplaint as Scenario,
    'respond_to_feedback_slow_responses': respondToFeedback as Scenario,
};

export function getAllScenarios(): Array<{ id: string; scenario: Scenario }> {
    return Object.entries(scenarioMap).map(([id, scenario]) => ({ id, scenario }));
}

export function getScenario(id: string): Scenario | undefined {
    return scenarioMap[id];
}
