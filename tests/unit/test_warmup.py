"""
Unit tests for the /warmup endpoint.

Tests the server-side debounce (10-min cooldown) and ensure_watch integration.
All Gmail/Firestore calls are mocked — no real GCP access needed.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def reset_warmup_state():
    """Reset the warmup debounce state between tests."""
    import service.main as main_module
    main_module._last_warmup_at = None
    yield
    main_module._last_warmup_at = None


@pytest.fixture
def client():
    """Flask test client."""
    from service.main import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


class TestWarmupEndpoint:
    """Tests for GET /warmup."""

    @patch('service.main.ensure_watch')
    @patch('service.main.get_gmail_service')
    def test_first_call_triggers_watch_check(self, mock_gmail, mock_watch, client):
        """First warmup call should call ensure_watch and return 'checked'."""
        mock_gmail.return_value = MagicMock()

        response = client.get('/warmup')
        data = response.get_json()

        assert response.status_code == 200
        assert data['status'] == 'ok'
        assert data['watch'] == 'checked'
        mock_gmail.assert_called_once()
        mock_watch.assert_called_once()

    @patch('service.main.ensure_watch')
    @patch('service.main.get_gmail_service')
    def test_second_call_within_cooldown_is_skipped(self, mock_gmail, mock_watch, client):
        """Second call within 10 minutes should skip ensure_watch."""
        mock_gmail.return_value = MagicMock()

        # First call — triggers watch
        response1 = client.get('/warmup')
        assert response1.get_json()['watch'] == 'checked'

        # Second call — should be skipped
        response2 = client.get('/warmup')
        data2 = response2.get_json()

        assert response2.status_code == 200
        assert data2['status'] == 'ok'
        assert data2['watch'] == 'skipped'
        assert data2['reason'] == 'cooldown'

        # ensure_watch should only have been called once
        mock_gmail.assert_called_once()
        mock_watch.assert_called_once()

    @patch('service.main.ensure_watch')
    @patch('service.main.get_gmail_service')
    def test_call_after_cooldown_triggers_watch_again(self, mock_gmail, mock_watch, client):
        """After cooldown expires, ensure_watch should be called again."""
        import service.main as main_module
        mock_gmail.return_value = MagicMock()

        # First call
        client.get('/warmup')
        assert mock_watch.call_count == 1

        # Simulate cooldown expiry by backdating the timestamp
        main_module._last_warmup_at = datetime.now(timezone.utc) - timedelta(minutes=11)

        # Second call — should trigger watch again
        response = client.get('/warmup')
        data = response.get_json()

        assert data['watch'] == 'checked'
        assert mock_watch.call_count == 2

    @patch('service.main.ensure_watch', side_effect=Exception("Gmail quota exceeded"))
    @patch('service.main.get_gmail_service')
    def test_watch_failure_still_returns_200(self, mock_gmail, mock_watch, client):
        """Warmup should return 200 even if ensure_watch fails."""
        mock_gmail.return_value = MagicMock()

        response = client.get('/warmup')
        data = response.get_json()

        assert response.status_code == 200
        assert data['status'] == 'ok'
        assert data['watch'] == 'error'
        assert 'Gmail quota' in data['detail']

    @patch('service.main.ensure_watch', side_effect=Exception("fail"))
    @patch('service.main.get_gmail_service')
    def test_watch_failure_sets_cooldown(self, mock_gmail, mock_watch, client):
        """Even failed watch checks should set the cooldown to avoid retry storms."""
        mock_gmail.return_value = MagicMock()

        # First call — fails but sets cooldown
        client.get('/warmup')

        # Second call — should be skipped (not retried)
        response = client.get('/warmup')
        assert response.get_json()['watch'] == 'skipped'
        assert mock_watch.call_count == 1  # only called once


class TestHealthEndpoint:
    """Tests for GET /health — simple liveness check."""

    def test_returns_200_ok(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.data.decode() == 'OK'
