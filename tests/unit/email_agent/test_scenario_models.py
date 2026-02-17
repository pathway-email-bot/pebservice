"""
Unit tests for service/email_agent/scenario_models.py.

Tests the Scenario dataclass: required fields, defaults, immutability,
and the InteractionType enum.
"""

import pytest

from service.email_agent.scenario_models import Scenario, InteractionType


class TestInteractionType:
    """Tests for the InteractionType enum."""

    def test_initiate_value(self):
        assert InteractionType.INITIATE == "initiate"
        assert InteractionType.INITIATE.value == "initiate"

    def test_reply_value(self):
        assert InteractionType.REPLY == "reply"
        assert InteractionType.REPLY.value == "reply"

    def test_string_comparison(self):
        """InteractionType(str, Enum) must compare equal to plain strings."""
        assert InteractionType.INITIATE == "initiate"
        assert InteractionType.REPLY == "reply"

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            InteractionType("respond")


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
            counterpart_context="You know the student missed a meeting.",
            grading_focus="Clarity",
            starter_sender_name="John",
            starter_subject="Subject",
            starter_email_body="Hello student",
            starter_email_generation_hint="Keep it short",
        )
        assert s.name == "Test Scenario"
        assert s.interaction_type == InteractionType.INITIATE
        assert s.interaction_type == "initiate"  # str comparison still works
        assert s.counterpart_context == "You know the student missed a meeting."
        assert s.starter_email_body == "Hello student"

    def test_defaults(self):
        s = Scenario(
            name="Test",
            description="Desc",
            environment="remote",
            counterpart_role="Boss",
            student_task="Task",
        )
        assert s.interaction_type == InteractionType.INITIATE
        assert s.counterpart_style == ""
        assert s.counterpart_context == ""
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
        assert s.interaction_type == InteractionType.REPLY
        assert s.interaction_type == "reply"  # str comparison works

    def test_string_coercion_in_post_init(self):
        """Plain string 'initiate' should be coerced to InteractionType.INITIATE."""
        s = Scenario(
            name="Test",
            description="Desc",
            environment="remote",
            counterpart_role="Boss",
            student_task="Task",
            interaction_type="initiate",
        )
        assert isinstance(s.interaction_type, InteractionType)

    def test_enum_value_accepted_directly(self):
        """Passing the enum directly should work."""
        s = Scenario(
            name="Test",
            description="Desc",
            environment="remote",
            counterpart_role="Boss",
            student_task="Task",
            interaction_type=InteractionType.REPLY,
        )
        assert s.interaction_type == InteractionType.REPLY

    def test_invalid_interaction_type_raises(self):
        """Invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            Scenario(
                name="Test",
                description="Desc",
                environment="remote",
                counterpart_role="Boss",
                student_task="Task",
                interaction_type="respond",
            )
