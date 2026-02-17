"""
Unit tests for service/secrets.py.

All Secret Manager interactions are mocked — no real GCP calls.
"""

from unittest.mock import patch, MagicMock

import pytest


class TestGetProjectId:
    """Tests for get_project_id()."""

    def setup_method(self):
        """Reset caches between tests."""
        from service.secrets import _reset_caches
        _reset_caches()

    def teardown_method(self):
        from service.secrets import _reset_caches
        _reset_caches()

    def test_reads_from_gcp_project_env(self):
        with patch.dict("os.environ", {"GCP_PROJECT": "my-project"}, clear=False):
            from service.secrets import get_project_id
            assert get_project_id() == "my-project"

    def test_reads_from_google_cloud_project_env(self):
        with patch.dict(
            "os.environ",
            {"GOOGLE_CLOUD_PROJECT": "other-project"},
            clear=False,
        ):
            # Make sure GCP_PROJECT is not set
            import os
            os.environ.pop("GCP_PROJECT", None)
            from service.secrets import get_project_id, _reset_caches
            _reset_caches()
            assert get_project_id() == "other-project"

    def test_caches_result(self):
        with patch.dict("os.environ", {"GCP_PROJECT": "cached-project"}, clear=False):
            from service.secrets import get_project_id, _reset_caches
            _reset_caches()
            result1 = get_project_id()
            result2 = get_project_id()
            assert result1 == result2 == "cached-project"


class TestGetSecret:
    """Tests for get_secret()."""

    def setup_method(self):
        from service.secrets import _reset_caches
        _reset_caches()

    def teardown_method(self):
        from service.secrets import _reset_caches
        _reset_caches()

    def test_fetches_and_strips_secret(self):
        with patch.dict("os.environ", {"GCP_PROJECT": "test-proj"}, clear=False):
            with patch("service.secrets.secretmanager") as mock_sm:
                mock_client = MagicMock()
                mock_sm.SecretManagerServiceClient.return_value = mock_client

                mock_response = MagicMock()
                mock_response.payload.data.decode.return_value = "  my-secret-value  \n"
                mock_client.access_secret_version.return_value = mock_response

                from service.secrets import get_secret, _reset_caches
                _reset_caches()
                result = get_secret("my-secret")

                assert result == "my-secret-value"
                mock_client.access_secret_version.assert_called_once()


class TestGetOpenaiApiKey:
    """Tests for get_openai_api_key()."""

    def setup_method(self):
        from service.secrets import _reset_caches
        _reset_caches()

    def teardown_method(self):
        from service.secrets import _reset_caches
        _reset_caches()

    def test_returns_key_from_secret_manager(self):
        with patch("service.secrets.get_secret", return_value="sk-test-key"):
            from service.secrets import get_openai_api_key
            assert get_openai_api_key() == "sk-test-key"

    def test_falls_back_to_env_var(self):
        with patch("service.secrets.get_secret", side_effect=Exception("no SM")):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-env-key"}, clear=False):
                from service.secrets import get_openai_api_key
                assert get_openai_api_key() == "sk-env-key"

    def test_returns_none_when_both_fail(self):
        with patch("service.secrets.get_secret", side_effect=Exception("no SM")):
            with patch.dict("os.environ", {}, clear=False):
                import os
                os.environ.pop("OPENAI_API_KEY", None)
                from service.secrets import get_openai_api_key
                assert get_openai_api_key() is None
