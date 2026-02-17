"""
Unit tests for service/auth.py.

Firebase Admin interactions are mocked — no real Firebase calls.
"""

from unittest.mock import patch, MagicMock

import pytest


class TestVerifyToken:
    """Tests for verify_token()."""

    def test_returns_email_for_valid_token(self):
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer valid-token"

        with patch("service.auth.firebase_auth") as mock_fb:
            mock_fb.verify_id_token.return_value = {"email": "student@example.com"}

            from service.auth import verify_token
            result = verify_token(mock_request)

            assert result == "student@example.com"
            mock_fb.verify_id_token.assert_called_once_with("valid-token")

    def test_returns_none_for_missing_header(self):
        mock_request = MagicMock()
        mock_request.headers.get.return_value = ""

        from service.auth import verify_token
        result = verify_token(mock_request)

        assert result is None

    def test_returns_none_for_non_bearer_header(self):
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Basic abc123"

        from service.auth import verify_token
        result = verify_token(mock_request)

        assert result is None

    def test_returns_none_for_invalid_token(self):
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer bad-token"

        with patch("service.auth.firebase_auth") as mock_fb:
            mock_fb.verify_id_token.side_effect = Exception("Invalid token")

            from service.auth import verify_token
            result = verify_token(mock_request)

            assert result is None
