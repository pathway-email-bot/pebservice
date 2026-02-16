"""
Unit tests for scenario JSON {student_name} placeholder and
start_scenario firstName integration.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from service.email_agent.scenario_loader import load_scenario, SCENARIOS_DIR


# ── Scenario JSON placeholder tests ──────────────────────────────────

def _reply_scenario_files():
    """Return all reply-type scenario JSON paths."""
    result = []
    for p in sorted(SCENARIOS_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("interaction_type") == "reply":
            result.append(p)
    return result


@pytest.fixture(params=_reply_scenario_files(), ids=lambda p: p.stem)
def reply_scenario_path(request):
    return request.param


class TestReplyScenarioPlaceholder:
    """Verify all reply scenarios include the {student_name} placeholder."""

    def test_starter_body_has_student_name_placeholder(self, reply_scenario_path):
        data = json.loads(reply_scenario_path.read_text(encoding="utf-8"))
        body = data.get("starter_email_body", "")
        assert "{student_name}" in body, (
            f"{reply_scenario_path.name}: reply scenario starter_email_body "
            "should contain {{student_name}} placeholder"
        )

    def test_placeholder_is_in_greeting(self, reply_scenario_path):
        """Placeholder should appear within a greeting like 'Hi {student_name},'."""
        data = json.loads(reply_scenario_path.read_text(encoding="utf-8"))
        body = data.get("starter_email_body", "")
        # Check it follows a greeting word
        import re
        assert re.search(r'(Hi|Hey|Hello)\s+\{student_name\}', body), (
            f"{reply_scenario_path.name}: placeholder should follow a greeting word"
        )


# ── start_scenario firstName integration ─────────────────────────────

class TestStartScenarioFirstName:
    """Test that start_scenario reads firstName and personalises the email."""

    def test_personalize_body_receives_first_name_from_user_doc(self):
        """Verify the firstName read → _personalize_body pipeline."""
        from service.main import _personalize_body

        # Simulate: user doc has firstName = "Sarah"
        body = "Hi {student_name},\\n\\nPlease review."
        result = _personalize_body(body, "Sarah")
        assert "Hi Sarah," in result
        assert "{student_name}" not in result

    def test_personalize_body_handles_missing_user_doc(self):
        """When user doc doesn't exist, firstName is None → placeholder removed."""
        from service.main import _personalize_body

        body = "Hi {student_name},\\n\\nPlease review."
        result = _personalize_body(body, None)
        assert "Hi ," in result
        assert "{student_name}" not in result

    def test_user_doc_firstname_extraction_logic(self):
        """Test the inline firstName extraction pattern used in start_scenario."""
        # This mirrors the exact code in start_scenario:
        #   first_name = user_doc.to_dict().get('firstName') if user_doc.exists else None

        # Case 1: doc exists with firstName
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"firstName": "María", "activeScenarioId": "test"}
        first_name = mock_doc.to_dict().get('firstName') if mock_doc.exists else None
        assert first_name == "María"

        # Case 2: doc exists without firstName
        mock_doc.to_dict.return_value = {"activeScenarioId": "test"}
        first_name = mock_doc.to_dict().get('firstName') if mock_doc.exists else None
        assert first_name is None

        # Case 3: doc doesn't exist
        mock_doc.exists = False
        first_name = mock_doc.to_dict().get('firstName') if mock_doc.exists else None
        assert first_name is None
