"""Quick manual check of recent Firestore attempts."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import firebase_admin
from firebase_admin import firestore

os.environ.setdefault('GOOGLE_CLOUD_PROJECT', 'pathway-email-bot-6543')
os.environ.setdefault('GCLOUD_PROJECT', 'pathway-email-bot-6543')

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(options={'projectId': 'pathway-email-bot-6543'})

db = firestore.Client(database='pathway')

print("=== Recent attempts for michaeltreynolds.test@gmail.com ===\n")
attempts = (db.collection('users')
    .document('michaeltreynolds.test@gmail.com')
    .collection('attempts')
    .order_by('createdAt', direction=firestore.Query.DESCENDING)
    .limit(5)
    .get())

for a in attempts:
    d = a.to_dict()
    print(f"ID: {a.id}")
    print(f"  status:    {d.get('status')}")
    print(f"  score:     {d.get('score')}")
    print(f"  scenario:  {d.get('scenarioId')}")
    print(f"  created:   {d.get('createdAt')}")
    print(f"  feedback:  {str(d.get('feedback', ''))[:80]}")
    print()
