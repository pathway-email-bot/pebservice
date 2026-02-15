"""
Local test: AI grading logic against a real OpenAI call.

Imports EmailAgent directly and grades a hardcoded student email.
No Gmail, no deployed function, no Pub/Sub — just scenario + rubric + OpenAI.

This gives fast feedback on whether the grading pipeline still works
without waiting for the full email round-trip.

Run:  python -m pytest tests/local/test_grading_logic.py -v --timeout=30
Cost: ~$0.01 per run (1 OpenAI API call)
"""

import os
from pathlib import Path

import pytest

PROJECT_ID = "pathway-email-bot-6543"
SERVICE_DIR = Path(__file__).resolve().parent.parent.parent / "service"


def _get_secret(name: str) -> str:
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    full_name = f"projects/{PROJECT_ID}/secrets/{name}/versions/latest"
    response = client.access_secret_version(request={"name": full_name})
    return response.payload.data.decode("UTF-8").strip()


@pytest.fixture(scope="module")
def openai_api_key():
    """Get the OpenAI API key from Secret Manager."""
    return _get_secret("openai-api-key")


class TestGradingLogic:
    """Verify AI grading works correctly against a real OpenAI call."""

    def test_grade_missed_standup_email(self, openai_api_key):
        """Grade a decent email and expect a reasonable score."""
        from service.email_agent.scenario_loader import load_scenario
        from service.email_agent.email_agent import EmailAgent, EmailMessage

        scenario_path = SERVICE_DIR / "email_agent" / "scenarios" / "missed_remote_standup.json"
        scenario = load_scenario(scenario_path)

        agent = EmailAgent(scenario=scenario, api_key=openai_api_key)

        # Build the starter thread (what the "manager" sent first)
        starter_thread = agent.build_starter_thread()

        # A decent student email
        student_email = EmailMessage(
            sender="student@example.com",
            subject="Re: Missed Remote Standup",
            body=(
                "Hi team,\n\n"
                "I sincerely apologize for missing this morning's standup. "
                "I had a late night debugging a production issue and overslept.\n\n"
                "Here's my update:\n"
                "Yesterday: Completed the API endpoint refactoring (PR #142).\n"
                "Today: I'll finish the database migration script.\n"
                "Blockers: I need staging database credentials from DevOps.\n\n"
                "I'll make sure to set a backup alarm going forward. "
                "Sorry for the inconvenience.\n\n"
                "Best regards"
            ),
        )

        result = agent.evaluate_and_respond(
            prior_thread=starter_thread,
            student_email=student_email,
        )

        # The grading result should be structurally valid
        assert result.grading is not None
        assert isinstance(result.grading.total_score, int)
        assert result.grading.total_score >= 0
        assert result.grading.max_total_score > 0
        assert len(result.grading.overall_comment) > 10, "Should have substantive feedback"

        # The counterpart reply should exist
        assert result.counterpart_reply is not None
        assert len(result.counterpart_reply) > 10, "Should have a real reply"

    def test_grade_poor_email_scores_lower(self, openai_api_key):
        """A minimal/poor email should score lower than a good one."""
        from service.email_agent.scenario_loader import load_scenario
        from service.email_agent.email_agent import EmailAgent, EmailMessage

        scenario_path = SERVICE_DIR / "email_agent" / "scenarios" / "missed_remote_standup.json"
        scenario = load_scenario(scenario_path)

        agent = EmailAgent(scenario=scenario, api_key=openai_api_key)
        starter_thread = agent.build_starter_thread()

        # A very poor student email
        student_email = EmailMessage(
            sender="student@example.com",
            subject="Re: Missed Remote Standup",
            body="sorry i missed it. wont happen again",
        )

        result = agent.evaluate_and_respond(
            prior_thread=starter_thread,
            student_email=student_email,
        )

        assert result.grading is not None
        assert isinstance(result.grading.total_score, int)
        # A poor email should score below 70% of max
        ratio = result.grading.total_score / result.grading.max_total_score
        assert ratio < 0.7, (
            f"Poor email scored too high: {result.grading.total_score}/{result.grading.max_total_score} "
            f"({ratio:.0%})"
        )
