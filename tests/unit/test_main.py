"""
Unit tests for service/main.py helper functions.

Tests get_header (case-insensitive header lookup) without any external
service dependencies.
"""

import pytest

from service.main import get_header


class TestGetHeader:
    """Tests for case-insensitive email header lookup."""

    SAMPLE_HEADERS = [
        {"name": "From", "value": "alice@example.com"},
        {"name": "Subject", "value": "Test Subject"},
        {"name": "Message-ID", "value": "<abc123@mail.example.com>"},
        {"name": "Content-Type", "value": "text/plain"},
    ]

    def test_exact_case_match(self):
        assert get_header(self.SAMPLE_HEADERS, "From") == "alice@example.com"

    def test_case_insensitive_match(self):
        assert get_header(self.SAMPLE_HEADERS, "from") == "alice@example.com"
        assert get_header(self.SAMPLE_HEADERS, "FROM") == "alice@example.com"

    def test_subject(self):
        assert get_header(self.SAMPLE_HEADERS, "subject") == "Test Subject"

    def test_message_id_mixed_case(self):
        assert get_header(self.SAMPLE_HEADERS, "message-id") == "<abc123@mail.example.com>"
        assert get_header(self.SAMPLE_HEADERS, "Message-Id") == "<abc123@mail.example.com>"

    def test_missing_header_returns_default(self):
        assert get_header(self.SAMPLE_HEADERS, "X-Custom") == ""

    def test_missing_header_with_custom_default(self):
        assert get_header(self.SAMPLE_HEADERS, "X-Custom", "fallback") == "fallback"

    def test_empty_headers(self):
        assert get_header([], "From") == ""

    def test_returns_first_match(self):
        """If multiple headers with same name, returns the first."""
        headers = [
            {"name": "From", "value": "first@example.com"},
            {"name": "From", "value": "second@example.com"},
        ]
        assert get_header(headers, "from") == "first@example.com"
