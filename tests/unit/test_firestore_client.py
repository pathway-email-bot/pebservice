"""
Unit tests for service/firestore_client.py.

All Firestore interactions are mocked — no real database calls.
"""

from unittest.mock import patch, MagicMock

import pytest


class TestGetActiveScenario:
    """Tests for get_active_scenario."""

    def test_returns_tuple_when_active(self):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "activeScenarioId": "missed_remote_standup",
            "activeAttemptId": "abc123",
        }

        with patch("service.firestore_client.get_firestore_client") as mock_client:
            mock_db = MagicMock()
            mock_client.return_value = mock_db
            mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

            from service.firestore_client import get_active_scenario
            result = get_active_scenario("test@example.com")

        assert result == ("missed_remote_standup", "abc123")

    def test_returns_none_for_nonexistent_user(self):
        mock_doc = MagicMock()
        mock_doc.exists = False

        with patch("service.firestore_client.get_firestore_client") as mock_client:
            mock_db = MagicMock()
            mock_client.return_value = mock_db
            mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

            from service.firestore_client import get_active_scenario
            result = get_active_scenario("nonexistent@example.com")

        assert result is None

    def test_returns_none_when_no_active_scenario(self):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {}

        with patch("service.firestore_client.get_firestore_client") as mock_client:
            mock_db = MagicMock()
            mock_client.return_value = mock_db
            mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

            from service.firestore_client import get_active_scenario
            result = get_active_scenario("user@example.com")

        assert result is None


class TestUpdateAttemptGraded:
    """Tests for update_attempt_graded."""

    def test_updates_attempt_document(self):
        with patch("service.firestore_client.get_firestore_client") as mock_client:
            mock_db = MagicMock()
            mock_client.return_value = mock_db

            mock_attempt_ref = MagicMock()
            mock_db.collection.return_value.document.return_value \
                .collection.return_value.document.return_value = mock_attempt_ref

            from service.firestore_client import update_attempt_graded
            update_attempt_graded(
                "test@example.com", "abc123", 18, 25, "Good work!",
                rubric_scores=[
                    {"name": "Tone & respect", "score": 4, "maxScore": 5, "justification": "Good tone."},
                    {"name": "Clarity", "score": 5, "maxScore": 5, "justification": "Very clear."},
                ],
                revision_example="Dear Manager, I apologize for..."
            )

            mock_attempt_ref.update.assert_called_once()
            call_args = mock_attempt_ref.update.call_args[0][0]
            assert call_args["status"] == "graded"
            assert call_args["score"] == 18
            assert call_args["maxScore"] == 25
            assert call_args["feedback"] == "Good work!"
            assert len(call_args["rubricScores"]) == 2
            assert call_args["rubricScores"][0]["name"] == "Tone & respect"
            assert call_args["rubricScores"][0]["justification"] == "Good tone."
            assert call_args["revisionExample"] == "Dear Manager, I apologize for..."
