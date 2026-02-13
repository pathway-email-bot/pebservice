"""
Unit tests for service/email_agent/email_agent.py.

Tests data models and the _thread_to_text helper. LLM calls are not tested
here (those would be integration tests).
"""

import pytest

from service.email_agent.email_agent import (
    EmailMessage,
    RubricScoreResult,
    GradingResult,
    EvaluationAndReply,
    _thread_to_text,
)


class TestEmailMessage:
    def test_creation(self):
        msg = EmailMessage(sender="test@example.com", subject="Hello", body="Hi there")
        assert msg.sender == "test@example.com"
        assert msg.subject == "Hello"
        assert msg.body == "Hi there"

    def test_frozen(self):
        msg = EmailMessage(sender="a", subject="b", body="c")
        with pytest.raises(AttributeError):
            msg.sender = "changed"


class TestRubricScoreResult:
    def test_creation(self):
        score = RubricScoreResult(name="Tone", score=4, max_score=5)
        assert score.name == "Tone"
        assert score.score == 4
        assert score.max_score == 5


class TestGradingResult:
    def test_creation(self):
        scores = [
            RubricScoreResult(name="Tone", score=4, max_score=5),
            RubricScoreResult(name="Clarity", score=3, max_score=5),
        ]
        result = GradingResult(
            scenario_name="test",
            scores=scores,
            total_score=7,
            max_total_score=10,
            overall_comment="Good work",
            revision_example="Better version",
            model_info={"model_name": "gpt-4o"},
            raw_json={"scores": []},
        )
        assert result.total_score == 7
        assert result.max_total_score == 10
        assert len(result.scores) == 2


class TestEvaluationAndReply:
    def test_creation(self):
        grading = GradingResult(
            scenario_name="test",
            scores=[],
            total_score=0,
            max_total_score=0,
            overall_comment="",
            revision_example="",
            model_info={},
            raw_json={},
        )
        result = EvaluationAndReply(grading=grading, counterpart_reply="Thank you")
        assert result.counterpart_reply == "Thank you"
        assert result.grading.scenario_name == "test"


class TestThreadToText:
    def test_empty_thread(self):
        assert _thread_to_text([]) == "(no prior emails yet)"

    def test_single_message(self):
        msg = EmailMessage(sender="Alice", subject="Test", body="Hello!")
        result = _thread_to_text([msg])
        assert "Message 1" in result
        assert "Alice" in result
        assert "Hello!" in result

    def test_multiple_messages(self):
        msgs = [
            EmailMessage(sender="Alice", subject="First", body="Hello"),
            EmailMessage(sender="Bob", subject="Re: First", body="Hi back"),
        ]
        result = _thread_to_text(msgs)
        assert "Message 1" in result
        assert "Message 2" in result
        assert "Alice" in result
        assert "Bob" in result
