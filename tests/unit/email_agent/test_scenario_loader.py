"""
Unit tests for service/email_agent/scenario_loader.py.

Validates that all scenario JSON files load correctly into Scenario dataclasses,
and tests loader edge cases.
"""

import json
from pathlib import Path

import pytest

from service.email_agent.scenario_loader import load_scenario, SCENARIOS_DIR
from service.email_agent.scenario_models import Scenario


# ── Discover all scenario files for parametrized tests ────────────────

def _scenario_files():
    return sorted(SCENARIOS_DIR.glob("*.json"))


REQUIRED_FIELDS = {"name", "description", "environment", "counterpart_role", "student_task"}

KNOWN_FIELDS = REQUIRED_FIELDS | {
    "interaction_type", "counterpart_style", "counterpart_context", "grading_focus",
    "starter_sender_name", "starter_subject", "starter_email_body",
    "starter_email_generation_hint",
}


@pytest.fixture(params=_scenario_files(), ids=lambda p: p.stem)
def scenario_path(request):
    return request.param


# ── Per-file validation tests ─────────────────────────────────────────

class TestScenarioJsonValidation:
    def test_is_valid_json(self, scenario_path):
        """File must parse as a JSON object."""
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{scenario_path.name} must be a JSON object"

    def test_has_required_fields(self, scenario_path):
        """Every scenario must include all required fields."""
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        missing = REQUIRED_FIELDS - set(data.keys())
        assert not missing, f"{scenario_path.name} missing: {missing}"

    def test_no_unknown_fields(self, scenario_path):
        """Catch typos or forgotten fields that won't map to the dataclass."""
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        unknown = set(data.keys()) - KNOWN_FIELDS
        assert not unknown, (
            f"{scenario_path.name} has unknown fields: {unknown}. "
            "Add to Scenario dataclass or remove from JSON."
        )

    def test_interaction_type_valid(self, scenario_path):
        """interaction_type must be 'initiate' or 'reply' if present."""
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        if "interaction_type" in data:
            from service.email_agent.scenario_models import InteractionType
            assert data["interaction_type"] in (
                InteractionType.INITIATE.value,
                InteractionType.REPLY.value,
            ), (
                f"{scenario_path.name}: got '{data['interaction_type']}'"
            )

    def test_student_task_mentions_counterpart_name(self, scenario_path):
        """student_task should mention the counterpart by name so students know who to address."""
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        sender = data.get("starter_sender_name", "")
        task = data.get("student_task", "")
        if not sender:
            return  # no sender defined, skip
        # Extract name parts: "Karen Lopez (Office Manager)" → ["Karen", "Lopez"]
        import re
        name_parts = re.split(r'[^a-zA-Z]+', sender)
        name_parts = [p for p in name_parts if len(p) > 1]  # skip single chars
        # At least the first and last name should appear in student_task
        missing = [p for p in name_parts[:2] if p not in task]
        assert not missing, (
            f"{scenario_path.name}: student_task should mention counterpart name. "
            f"Missing: {missing} from '{sender}'"
        )

    def test_reply_scenario_has_starter_body(self, scenario_path):
        """Reply scenarios must have a static starter_email_body."""
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        if data.get("interaction_type") == "reply":
            body = data.get("starter_email_body")
            assert body and isinstance(body, str) and len(body) > 10, (
                f"{scenario_path.name}: reply scenario must have a non-empty starter_email_body"
            )

    def test_loads_into_dataclass(self, scenario_path):
        """Must load into Scenario without errors."""
        scenario = load_scenario(scenario_path)
        assert isinstance(scenario, Scenario)
        assert scenario.name
        assert scenario.student_task


# ── Loader function tests ────────────────────────────────────────────

class TestLoadScenario:
    def test_load_by_name(self):
        """Can load by scenario name string (without extension)."""
        scenario = load_scenario("missed_remote_standup")
        assert scenario.name

    def test_load_by_full_path(self):
        """Can load by full Path object."""
        path = SCENARIOS_DIR / "missed_remote_standup.json"
        scenario = load_scenario(path)
        assert scenario.name

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_scenario("totally_fake_scenario_that_does_not_exist")


# ── Sanity checks ────────────────────────────────────────────────────

def test_scenario_count():
    """We should have at least one scenario."""
    assert len(_scenario_files()) >= 1
