"""
Unit tests for service/email_agent/rubric_loader.py.

Validates all rubric JSON files and tests loader edge cases.
"""

import json
from pathlib import Path

import pytest

from service.email_agent.rubric_loader import load_rubric, RubricDefinition

RUBRICS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "service" / "email_agent" / "rubrics"


# ── Discover all rubric files ─────────────────────────────────────────

def _rubric_files():
    return sorted(RUBRICS_DIR.glob("*.json"))


@pytest.fixture(params=_rubric_files(), ids=lambda p: p.stem)
def rubric_path(request):
    return request.param


# ── Per-file validation tests ─────────────────────────────────────────

class TestRubricJsonValidation:
    def test_is_valid_json(self, rubric_path):
        data = json.loads(rubric_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{rubric_path.name} must be a JSON object"

    def test_has_items(self, rubric_path):
        data = json.loads(rubric_path.read_text(encoding="utf-8"))
        assert "items" in data, f"{rubric_path.name} missing 'items'"
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0, "Rubric must have at least one item"

    def test_items_structure(self, rubric_path):
        data = json.loads(rubric_path.read_text(encoding="utf-8"))
        for i, item in enumerate(data["items"]):
            assert "name" in item, f"Item #{i+1} missing 'name'"
            assert "description" in item, f"Item #{i+1} missing 'description'"
            assert isinstance(item["name"], str)
            assert isinstance(item["description"], str)
            if "max_score" in item:
                assert isinstance(item["max_score"], int)
                assert item["max_score"] > 0

    def test_loads_into_dataclass(self, rubric_path):
        rubric = load_rubric(rubric_path)
        assert isinstance(rubric, RubricDefinition)
        assert rubric.name
        assert len(rubric.items) > 0
        for item in rubric.items:
            assert item.name
            assert item.max_score > 0


# ── Loader edge cases ────────────────────────────────────────────────

class TestLoadRubric:
    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_rubric("totally_fake_rubric.json")


# ── Sanity checks ────────────────────────────────────────────────────

def test_rubric_count():
    """We should have at least one rubric."""
    assert len(_rubric_files()) >= 1
