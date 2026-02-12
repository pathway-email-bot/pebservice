"""
Firestore client for managing user attempts and scenarios.
"""
from google.cloud import firestore
from datetime import datetime
from typing import Optional, Dict, Any
import uuid

def get_firestore_client():
    """Returns Firestore client (uses default credentials in Cloud Functions)"""
    return firestore.Client(database='pathway')

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

def update_attempt_graded(email: str, attempt_id: str, score: int, max_score: int, feedback: str):
    """
    Mark attempt as graded with results.
    
    Args:
        email: User's email address
        attempt_id: Attempt ID
        score: Score achieved
        max_score: Maximum possible score
        feedback: Feedback text
    """
    db = get_firestore_client()
    
    attempt_ref = db.collection('users').document(email).collection('attempts').document(attempt_id)
    attempt_ref.update({
        'status': 'graded',
        'score': score,
        'maxScore': max_score,
        'feedback': feedback,
        'gradedAt': firestore.SERVER_TIMESTAMP,
    })
    
    # Clear active scenario if this was the active one
    user_ref = db.collection('users').document(email)
    user_doc = user_ref.get()
    if user_doc.exists and user_doc.get('activeAttemptId') == attempt_id:
        user_ref.update({
            'activeScenarioId': None,
            'activeAttemptId': None,
        })
