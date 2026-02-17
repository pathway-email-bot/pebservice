"""
Shared Firestore test helpers — mutex and cleanup utilities.

Provides a test-account lock (Firestore-based mutex with auto-expiry)
and user document cleanup for integration/browser tests that share
the same test email account.

Usage as a pytest fixture:

    from tests.helpers.firestore_helpers import get_firestore_db, test_user_lock

    @pytest.fixture(autouse=True)
    def clean_test_user():
        db = get_firestore_db()
        with test_user_lock(db, "michaeltreynolds.test@gmail.com"):
            delete_user_document(db, "michaeltreynolds.test@gmail.com")
            yield
"""

import os
import time
import uuid
import socket
from contextlib import contextmanager

# Mutex config
LOCK_COLLECTION = "system"
LOCK_DOCUMENT = "test_account_lock"
LOCK_TTL = 300        # seconds — lock auto-expires after 5 min
LOCK_POLL = 3         # seconds between lock acquisition retries
LOCK_TIMEOUT = 120    # seconds — max wait to acquire lock


def get_firestore_db():
    """Get Firestore client for the 'pathway' database."""
    from google.cloud import firestore
    return firestore.Client(database="pathway")


def acquire_lock(db, lock_id: str | None = None) -> str:
    """
    Acquire a Firestore test-account lock with auto-expiry.

    Uses a transaction to atomically check-and-set. If the lock is held
    but expired (older than LOCK_TTL), it's considered released.

    Returns the owner string for logging/debugging.
    Raises TimeoutError if the lock can't be acquired within LOCK_TIMEOUT.
    """
    from google.cloud import firestore

    lock_ref = db.collection(LOCK_COLLECTION).document(LOCK_DOCUMENT)
    owner = f"{socket.gethostname()}-{os.getpid()}-{lock_id or uuid.uuid4().hex[:8]}"
    start = time.time()

    while time.time() - start < LOCK_TIMEOUT:
        @firestore.transactional
        def try_acquire(transaction):
            snap = lock_ref.get(transaction=transaction)
            now = time.time()

            if snap.exists:
                data = snap.to_dict()
                locked_at = data.get("locked_at", 0)
                if now - locked_at < LOCK_TTL:
                    return False  # lock is held and not expired

            # Lock is free (or expired) — claim it
            transaction.set(lock_ref, {
                "owner": owner,
                "locked_at": now,
            })
            return True

        txn = db.transaction()
        if try_acquire(txn):
            return owner

        time.sleep(LOCK_POLL)

    raise TimeoutError(f"Could not acquire test account lock within {LOCK_TIMEOUT}s")


def release_lock(db) -> None:
    """Release the test-account lock."""
    lock_ref = db.collection(LOCK_COLLECTION).document(LOCK_DOCUMENT)
    lock_ref.delete()


@contextmanager
def test_user_lock(db, label: str = "", log=None):
    """
    Context manager that acquires the test-account lock and releases on exit.

    The lock is held for the entire duration of the ``with`` block,
    including across ``yield`` in pytest fixtures.

    Args:
        log: optional callable for status messages (e.g. print or _log).
    """
    _print = log or (lambda msg: None)
    owner = acquire_lock(db, label)
    _print(f"Acquired test-account lock (owner: {owner})")
    try:
        yield owner
    finally:
        release_lock(db)
        _print("Released test-account lock")


def delete_user_document(db, email: str) -> int:
    """
    Delete a user's Firestore document and all subcollections.

    Returns the number of attempt documents deleted.

    This ensures the test exercises the real new-user flow (no user doc
    exists) and prevents unbounded growth of attempt documents from CI.
    """
    user_ref = db.collection("users").document(email)

    # Delete all attempts in the subcollection first
    attempts_ref = user_ref.collection("attempts")
    docs = list(attempts_ref.stream())
    for doc in docs:
        doc.reference.delete()

    # Delete the user doc itself
    user_ref.delete()
    return len(docs)
