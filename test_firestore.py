import firebase_admin
from firebase_admin import credentials, firestore

try:
    cred = credentials.Certificate('firebase-key.json')
    app = firebase_admin.initialize_app(cred)
    db = firestore.client()
    # Try to write
    db.collection('test').document('123').set({'a': 1})
    print("FIRESTORE WRITE SUCCESS")
    docs = db.collection('test').stream()
    print("FIRESTORE READ:", [d.id for d in docs])
except Exception as e:
    print(f"FIRESTORE ERROR: {e}")
