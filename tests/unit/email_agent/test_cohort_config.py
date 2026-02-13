"""
Unit tests for service/email_agent/cohort_config.py.

Tests the CohortConfig dataclass: defaults and immutability.
"""

import pytest

from service.email_agent.cohort_config import CohortConfig


class TestCohortConfig:
    def test_defaults(self):
        config = CohortConfig()
        assert config.student_program == "BYU-Pathway Worldwide"
        assert "developing countries" in config.student_background
        assert config.english_level == "intermediate"
        assert "unstable internet" in config.remote_context
        assert "US-based" in config.employer_region

    def test_custom_values(self):
        config = CohortConfig(
            student_program="Custom Program",
            english_level="advanced",
        )
        assert config.student_program == "Custom Program"
        assert config.english_level == "advanced"
        # Other fields keep defaults
        assert "developing countries" in config.student_background

    def test_frozen(self):
        config = CohortConfig()
        with pytest.raises(AttributeError):
            config.english_level = "advanced"
