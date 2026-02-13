"""
Integration test: Firestore read/write on the 'pathway' database.

Creates a test attempt, reads it back, updates it, and cleans up. Uses a
dedicated test path so real user data is never touched.

Works both locally (via `gcloud auth application-default login`) and in
CI (via the GCP_SA_KEY service account).

Run: python -m pytest tests/integration/test_firestore.py -v
"""

import os
import uuid

import pytest

PROJECT_ID = "pathway-email-bot-6543"
TEST_USER = "integration-test@test.local"  # fake user, won't collide with real data


@pytest.fixture(scope="module")
def db():
    """Get a Firestore client pointing at the 'pathway' database."""
    import firebase_admin
    from google.cloud import firestore

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", PROJECT_ID)
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": PROJECT_ID})

    return firestore.Client(database="pathway")


@pytest.fixture
def attempt_ref(db):
    """Create a unique attempt doc ref, clean up after the test."""
    ref = (
        db.collection("users")
        .document(TEST_USER)
        .collection("attempts")
        .document(f"test-{uuid.uuid4().hex[:8]}")
    )
    yield ref
    # Cleanup — delete the doc if it exists
    ref.delete()


class TestFirestoreReadWrite:
    def test_create_and_read_attempt(self, attempt_ref):
        attempt_ref.set({
            "scenarioId": "test_scenario",
            "status": "pending",
        })

        doc = attempt_ref.get()
        assert doc.exists
        data = doc.to_dict()
        assert data["scenarioId"] == "test_scenario"
        assert data["status"] == "pending"

    def test_update_attempt_grading(self, attempt_ref):
        attempt_ref.set({
            "scenarioId": "test_scenario",
            "status": "pending",
        })

        attempt_ref.update({
            "status": "graded",
            "score": 15,
            "maxScore": 20,
            "feedback": "Good job on this test attempt.",
        })

        doc = attempt_ref.get()
        data = doc.to_dict()
        assert data["status"] == "graded"
        assert data["score"] == 15
        assert data["maxScore"] == 20
        assert "Good job" in data["feedback"]

    def test_user_doc_active_scenario(self, db):
        """Test setting/reading activeScenarioId on user doc."""
        user_ref = db.collection("users").document(TEST_USER)

        user_ref.set({
            "activeScenarioId": "test_scenario",
            "activeAttemptId": "test-attempt-123",
        }, merge=True)

        doc = user_ref.get()
        data = doc.to_dict()
        assert data["activeScenarioId"] == "test_scenario"
        assert data["activeAttemptId"] == "test-attempt-123"

        # Cleanup
        user_ref.delete()
