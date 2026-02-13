"""
Unit tests for service/email_agent/grading_serialization.py.

Tests round-trip serialization: GradingResult → storage dict → GradingResult.
"""

import pytest

from service.email_agent.email_agent import GradingResult, RubricScoreResult
from service.email_agent.grading_serialization import (
    grading_result_to_storage,
    grading_result_from_storage,
)


def _sample_grading_result():
    """Create a sample GradingResult for testing."""
    return GradingResult(
        scenario_name="missed_remote_standup",
        scores=[
            RubricScoreResult(name="Tone & respect", score=4, max_score=5),
            RubricScoreResult(name="Clarity & conciseness", score=3, max_score=5),
            RubricScoreResult(name="Structure", score=5, max_score=5),
        ],
        total_score=12,
        max_total_score=15,
        overall_comment="Good work! Your email was professional.",
        revision_example="Dear Manager, I apologize for missing...",
        model_info={"model_name": "gpt-4o", "temperature": 0.2},
        raw_json={"scores": [{"name": "Tone", "score": 4}]},
    )


class TestGradingResultToStorage:
    def test_contains_version(self):
        data = grading_result_to_storage(_sample_grading_result())
        assert data["version"] == 1

    def test_preserves_scenario_name(self):
        data = grading_result_to_storage(_sample_grading_result())
        assert data["scenario_name"] == "missed_remote_standup"

    def test_preserves_scores(self):
        data = grading_result_to_storage(_sample_grading_result())
        assert len(data["rubric_scores"]) == 3
        assert data["rubric_scores"][0] == {"name": "Tone & respect", "score": 4, "max_score": 5}

    def test_preserves_totals(self):
        data = grading_result_to_storage(_sample_grading_result())
        assert data["total_score"] == 12
        assert data["max_total_score"] == 15

    def test_preserves_comment(self):
        data = grading_result_to_storage(_sample_grading_result())
        assert "professional" in data["overall_comment"]

    def test_preserves_model_info(self):
        data = grading_result_to_storage(_sample_grading_result())
        assert data["model_info"]["model_name"] == "gpt-4o"


class TestGradingResultFromStorage:
    def test_rebuilds_scores(self):
        data = grading_result_to_storage(_sample_grading_result())
        result = grading_result_from_storage(data)
        assert len(result.scores) == 3
        assert result.scores[0].name == "Tone & respect"
        assert result.scores[0].score == 4

    def test_rebuilds_totals(self):
        data = grading_result_to_storage(_sample_grading_result())
        result = grading_result_from_storage(data)
        assert result.total_score == 12
        assert result.max_total_score == 15

    def test_rebuilds_comment(self):
        data = grading_result_to_storage(_sample_grading_result())
        result = grading_result_from_storage(data)
        assert result.overall_comment == "Good work! Your email was professional."


class TestRoundTrip:
    def test_full_round_trip(self):
        """GradingResult → dict → GradingResult should preserve all data."""
        original = _sample_grading_result()
        data = grading_result_to_storage(original)
        restored = grading_result_from_storage(data)

        assert restored.scenario_name == original.scenario_name
        assert restored.total_score == original.total_score
        assert restored.max_total_score == original.max_total_score
        assert restored.overall_comment == original.overall_comment
        assert restored.revision_example == original.revision_example
        assert len(restored.scores) == len(original.scores)
        for orig, rest in zip(original.scores, restored.scores):
            assert rest.name == orig.name
            assert rest.score == orig.score
            assert rest.max_score == orig.max_score

    def test_empty_scores(self):
        """Round-trip with empty scores should work."""
        data = {
            "scenario_name": "test",
            "rubric_scores": [],
            "total_score": 0,
            "max_total_score": 0,
            "overall_comment": "",
            "revision_example": "",
        }
        result = grading_result_from_storage(data)
        assert result.total_score == 0
        assert len(result.scores) == 0
