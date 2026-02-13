"""
Unit tests for service/email_agent/scenario_models.py.

Tests the Scenario dataclass: required fields, defaults, immutability.
"""

import pytest

from service.email_agent.scenario_models import Scenario


class TestScenario:
    def test_with_all_fields(self):
        s = Scenario(
            name="Test Scenario",
            description="A test scenario",
            environment="remote_workplace",
            counterpart_role="Manager",
            student_task="Write an email",
            interaction_type="initiate",
            counterpart_style="Professional",
            grading_focus="Clarity",
            starter_sender_name="John",
            starter_subject="Subject",
            starter_email_body="Hello student",
            starter_email_generation_hint="Keep it short",
        )
        assert s.name == "Test Scenario"
        assert s.interaction_type == "initiate"
        assert s.starter_email_body == "Hello student"

    def test_defaults(self):
        s = Scenario(
            name="Test",
            description="Desc",
            environment="remote",
            counterpart_role="Boss",
            student_task="Task",
        )
        assert s.interaction_type == "initiate"
        assert s.counterpart_style == ""
        assert s.grading_focus == ""
        assert s.starter_sender_name == "Jordan Smith (Manager)"
        assert s.starter_subject == "Regarding your work today"
        assert s.starter_email_body is None

    def test_frozen(self):
        s = Scenario(
            name="Test",
            description="Desc",
            environment="remote",
            counterpart_role="Boss",
            student_task="Task",
        )
        with pytest.raises(AttributeError):
            s.name = "Changed"

    def test_reply_type(self):
        s = Scenario(
            name="Reply Scenario",
            description="Desc",
            environment="remote",
            counterpart_role="Boss",
            student_task="Reply to the email",
            interaction_type="reply",
        )
        assert s.interaction_type == "reply"
