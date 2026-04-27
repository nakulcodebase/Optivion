import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')

if not API_KEY:
    print("API Key not found.")
    exit()

print(f"Testing API Key: {API_KEY[:10]}...")

origin = "San Francisco, CA"
destination = "San Jose, CA"

# Test 1: Directions API (Legacy)
print("\n--- Testing Directions API (Legacy) ---")
directions_url = f"https://maps.googleapis.com/maps/api/directions/json?origin={origin}&destination={destination}&key={API_KEY}"
res1 = requests.get(directions_url)
data1 = res1.json()
if data1.get('status') == 'OK':
    print("Directions API is ENABLED and WORKING.")
else:
    print(f"Directions API Error: {data1.get('status')} - {data1.get('error_message')}")

# Test 2: Routes API (New)
print("\n--- Testing Routes API ---")
routes_url = 'https://routes.googleapis.com/directions/v2:computeRoutes'
headers = {
    'Content-Type': 'application/json',
    'X-Goog-Api-Key': API_KEY,
    'X-Goog-FieldMask': 'routes.distanceMeters'
}
payload = {
    "origin": {"address": origin},
    "destination": {"address": destination},
    "travelMode": "DRIVE"
}
res2 = requests.post(routes_url, headers=headers, json=payload)
data2 = res2.json()
if 'error' in data2:
    print(f"Routes API Error: {data2['error'].get('message')}")
elif 'routes' in data2:
    print("Routes API is ENABLED and WORKING.")
else:
    print("Routes API Error: Unknown response:", data2)
