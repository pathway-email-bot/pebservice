"""
LOCAL DEBUG SCRIPT - DO NOT ADD TO CI PIPELINE

This script is for local testing of the email agent only.
It calls the OpenAI API, which costs money on every run.
Running this in CI would incur unnecessary API charges.

Usage:
    python local_debug_user_email.py
"""
import os
import sys
from email_agent.email_agent import EmailAgent, EmailMessage
from email_agent.scenario_models import Scenario
from email_agent.rubric import GLOBAL_RUBRIC

def test_user_email():
    # Setup
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return

    # Use a default scenario
    scenario = Scenario(
        name="Work Email Quality",
        description="Testing professional email communication.",
        role="Manager",
        task="Evaluate a student email about missing a standup.",
        starter_email_body="Hey, we missed you at the standup today. Is everything okay?"
    )

    agent = EmailAgent(api_key=api_key, scenario=scenario)

    student_email_content = """To whom it may concern,

My sincere apologies for missing standup this morning. There was a brief power outage that impacted my internet connection. I will send you an update on my efforts and cc Jill in as well. Today I don't have any blockers and plan to focus on the github issues that are assigned to me.

Please reach out if there are any important announcements that I missed or if there is anything you would like me to know before I dive in at 11 am your time today.

Best,
Student Name"""

    student_email = EmailMessage(
        subject="Apologies for missing standup",
        body=student_email_content,
        sender="student@example.com",
        recipient="bot@example.com"
    )

    print("--- Running AI Evaluation ---")
    result = agent.evaluate_and_respond(
        prior_thread=[],
        student_email=student_email,
        rubric=GLOBAL_RUBRIC
    )

    print("\n--- AI Response ---")
    print(result.counterpart_reply)
    print("\n--- Grading Summary ---")
    print(f"Total Score: {result.total_score}/{result.max_total_score}")
    print(f"Overall Comment: {result.overall_comment}")

if __name__ == "__main__":
    test_user_email()
