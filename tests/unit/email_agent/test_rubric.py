"""
Unit tests for service/email_agent/rubric.py.

Tests the RubricItem dataclass and GLOBAL_RUBRIC constant.
"""

import pytest

from service.email_agent.rubric import RubricItem, GLOBAL_RUBRIC


class TestRubricItem:
    def test_creation(self):
        item = RubricItem(name="Tone", description="Be polite")
        assert item.name == "Tone"
        assert item.description == "Be polite"
        assert item.max_score == 5  # default

    def test_custom_max_score(self):
        item = RubricItem(name="Tone", description="Be polite", max_score=10)
        assert item.max_score == 10

    def test_frozen(self):
        item = RubricItem(name="Tone", description="Be polite")
        with pytest.raises(AttributeError):
            item.name = "Changed"


class TestGlobalRubric:
    def test_has_items(self):
        assert len(GLOBAL_RUBRIC) >= 5

    def test_all_items_are_rubric_items(self):
        for item in GLOBAL_RUBRIC:
            assert isinstance(item, RubricItem)

    def test_all_items_have_description(self):
        for item in GLOBAL_RUBRIC:
            assert item.name
            assert item.description
            assert item.max_score > 0

    def test_expected_rubric_names(self):
        names = {item.name for item in GLOBAL_RUBRIC}
        assert "Tone & respect" in names
        assert "Clarity & conciseness" in names
        assert "Structure" in names
        assert "Task fulfillment" in names
