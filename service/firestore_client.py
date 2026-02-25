"""
Firestore client for managing user attempts and scenarios.
"""
from google.cloud import firestore
from datetime import datetime
from typing import Optional
import uuid

from .logging_utils import log_function

# Module-level cached client
_db: firestore.Client | None = None


@log_function
def get_firestore_client():
    """Returns cached Firestore client (uses default credentials in Cloud Functions)."""
    global _db
    if _db is None:
        _db = firestore.Client(database='pathway')
    return _db


def _reset_client():
    """Reset the cached client (for testing only)."""
    global _db
    _db = None

@log_function
def create_attempt(email: str, scenario_id: str) -> str:
    """
    Create new attempt for a user.
    
    Args:
        email: User's email address
        scenario_id: ID of the scenario
        
    Returns:
        attempt_id: Generated attempt ID
    """
    db = get_firestore_client()
    attempt_id = str(uuid.uuid4())
    
    # Create attempt document
    attempt_ref = db.collection('users').document(email).collection('attempts').document(attempt_id)
    attempt_ref.set({
        'scenarioId': scenario_id,
        'status': 'pending',
        'startedAt': firestore.SERVER_TIMESTAMP,
    })
    
    # Update user's active scenario
    user_ref = db.collection('users').document(email)
    user_ref.set({
        'activeScenarioId': scenario_id,
        'activeAttemptId': attempt_id,
    }, merge=True)
    
    return attempt_id

@log_function
def get_active_scenario(email: str) -> Optional[tuple[str, str]]:
    """
    Get the active scenario for a user.
    Reads activeScenarioId and activeAttemptId from the user document
    (set by create_attempt).
    
    Args:
        email: User's email address
        
    Returns:
        (scenario_id, attempt_id) or None if no active scenario
    """
    db = get_firestore_client()
    
    user_ref = db.collection('users').document(email)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        return None
    
    data = user_doc.to_dict()
    scenario_id = data.get('activeScenarioId')
    attempt_id = data.get('activeAttemptId')
    
    if scenario_id and attempt_id:
        return (scenario_id, attempt_id)
    return None

@log_function
def update_attempt_graded(
    email: str,
    attempt_id: str,
    score: int,
    max_score: int,
    feedback: str,
    rubric_scores: list | None = None,
    revision_example: str = "",
):
    """
    Mark attempt as graded with results.
    
    Args:
        email: User's email address
        attempt_id: Attempt ID
        score: Score achieved
        max_score: Maximum possible score
        feedback: Feedback text
        rubric_scores: Per-rubric breakdown (list of dicts with name/score/maxScore/justification)
        revision_example: Example improved version of the student's email
    """
    db = get_firestore_client()
    
    attempt_ref = db.collection('users').document(email).collection('attempts').document(attempt_id)
    update_data = {
        'status': 'graded',
        'score': score,
        'maxScore': max_score,
        'feedback': feedback,
        'gradedAt': firestore.SERVER_TIMESTAMP,
    }
    if rubric_scores is not None:
        update_data['rubricScores'] = rubric_scores
    if revision_example:
        update_data['revisionExample'] = revision_example
    attempt_ref.update(update_data)
    
    # Clear active scenario if this was the active one
    user_ref = db.collection('users').document(email)
    user_doc = user_ref.get()
    if user_doc.exists and user_doc.get('activeAttemptId') == attempt_id:
        user_ref.update({
            'activeScenarioId': None,
            'activeAttemptId': None,
        })


# ============================================================================
# Gmail History Cursor
# ============================================================================

_SYNC_DOC_PATH = ('system', 'gmail_sync')


def get_last_history_id() -> str | None:
    """Read the last-processed Gmail historyId from Firestore."""
    db = get_firestore_client()
    doc_ref = db.collection(_SYNC_DOC_PATH[0]).document(_SYNC_DOC_PATH[1])
    snap = doc_ref.get()
    if snap.exists:
        return snap.to_dict().get('lastHistoryId')
    return None


def update_last_history_id(history_id: str):
    """Write the last-processed Gmail historyId to Firestore."""
    db = get_firestore_client()
    doc_ref = db.collection(_SYNC_DOC_PATH[0]).document(_SYNC_DOC_PATH[1])
    doc_ref.set({'lastHistoryId': history_id}, merge=True)


# ============================================================================
# Attempt Claim (idempotent grading)
# ============================================================================


def claim_attempt_for_grading(email: str, attempt_id: str) -> bool:
    """Atomically claim an attempt for grading (pending → grading).

    Returns True if this caller won the claim, False if the attempt
    was already claimed or graded by another instance.
    """
    db = get_firestore_client()
    attempt_ref = (
        db.collection('users').document(email)
        .collection('attempts').document(attempt_id)
    )

    @firestore.transactional
    def _txn(transaction):
        snap = attempt_ref.get(transaction=transaction)
        if snap.exists and snap.to_dict().get('status') == 'pending':
            transaction.update(attempt_ref, {'status': 'grading'})
            return True
        return False

    return _txn(db.transaction())

