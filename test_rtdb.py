import firebase_admin
from firebase_admin import credentials, db

try:
    cred = credentials.Certificate('firebase-key.json')
    app = firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://optivion-4ae9f-default-rtdb.asia-southeast1.firebasedatabase.app'
    })
    ref = db.reference('test')
    ref.set({'a': 1})
    print("RTDB WRITE SUCCESS")
    print("RTDB READ:", ref.get())
except Exception as e:
    print(f"RTDB ERROR: {e}")
