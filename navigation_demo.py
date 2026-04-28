import os
import requests
import folium
import polyline
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from .env
API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')

if not API_KEY:
    raise ValueError("Google Maps API key not found in .env file.")

print("Google Maps API key loaded.")

# Define starting point and destination
origin = "Bsf Academy Tekanpur Gwalior"
destination = "Hyderabad"

print(f"Requesting directions from '{origin}' to '{destination}' via Routes API...")

# Use the Routes API directly since the legacy Directions API is disabled for this key
url = 'https://routes.googleapis.com/directions/v2:computeRoutes'
headers = {
    'Content-Type': 'application/json',
    'X-Goog-Api-Key': API_KEY,
    'X-Goog-FieldMask': 'routes.polyline.encodedPolyline,routes.legs,routes.distanceMeters,routes.duration'
}
payload = {
    "origin": {"address": origin},
    "destination": {"address": destination},
    "travelMode": "DRIVE"
}

response = requests.post(url, headers=headers, json=payload)
resp_data = response.json()

if 'error' in resp_data:
    print(f"Error getting route: {resp_data['error'].get('message', str(resp_data['error']))}")
    print("\nFalling back to a mock route for demonstration purposes...")
    # Mock data for San Francisco to San Jose
    start_coords = [37.7749, -122.4194]
    end_coords = [37.3382, -121.8863]
    coordinates = [
        (37.7749, -122.4194), (37.7699, -122.4100), (37.7600, -122.4000), 
        (37.6000, -122.3800), (37.5000, -122.3000), (37.4000, -122.1000), 
        (37.3382, -121.8863)
    ]
    distance_km = 76.5
    duration_min = 55
else:
    routes = resp_data.get('routes')
    if not routes:
        print("No route found.")
        exit()

    # Extract the route from API
    route = routes[0]
    leg = route['legs'][0]

    # Extract start and end coordinates
    start_location = leg['startLocation']['latLng']
    end_location = leg['endLocation']['latLng']
    start_coords = [start_location['latitude'], start_location['longitude']]
    end_coords = [end_location['latitude'], end_location['longitude']]

    # Extract and decode the polyline
    encoded_polyline = route['polyline']['encodedPolyline']
    coordinates = polyline.decode(encoded_polyline)
    
    distance_km = route.get('distanceMeters', 0) / 1000
    duration_sec = int(route.get('duration', '0s').replace('s', ''))
    duration_min = duration_sec // 60

print("Route data parsed. Creating interactive map with Folium...")

# Create a Folium map centered around the starting location
m = folium.Map(location=start_coords, zoom_start=10)

# Draw the route on the map
folium.PolyLine(locations=coordinates, color='#2563eb', weight=5, opacity=0.8).add_to(m)

# Add markers for origin and destination
folium.Marker(location=start_coords, popup=f"Start: {origin}", icon=folium.Icon(color="green", icon="play")).add_to(m)
folium.Marker(location=end_coords, popup=f"End: {destination}", icon=folium.Icon(color="red", icon="stop")).add_to(m)

# Save the map to an HTML file
output_file = "navigation_demo_map.html"
m.save(output_file)

print(f"Demo complete! Interactive map saved to {output_file}")
print(f"Distance: {distance_km} km")
print(f"Duration: {duration_min} mins")
print("\nOpen 'navigation_demo_map.html' in your web browser to see the visual route.")
