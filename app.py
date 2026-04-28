from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import googlemaps
import folium
import polyline
import os
import math
import json
import base64
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db as rtdb

load_dotenv() # Load variables from .env

app = Flask(__name__)
app.config['SECRET_KEY'] = 'optivion-secret-key'

API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY', '')

# Initialize Firebase Admin
db = None
try:
    cred = None
    
    # Try to load from environment variable (Vercel)
    firebase_key_base64 = os.environ.get('FIREBASE_SERVICE_ACCOUNT_BASE64')
    if firebase_key_base64:
        # Decode base64 to JSON
        firebase_key_json = base64.b64decode(firebase_key_base64).decode('utf-8')
        firebase_key_dict = json.loads(firebase_key_json)
        cred = credentials.Certificate(firebase_key_dict)
        print("Firebase initialized from environment variable (Vercel)")
    
    # Fall back to local file (for local development)
    elif os.path.exists('firebase-key.json'):
        cred = credentials.Certificate('firebase-key.json')
        print("Firebase initialized from local file")
    
    # Initialize app if credentials were loaded
    if cred:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://optivion-4ae9f-default-rtdb.asia-southeast1.firebasedatabase.app'
            })
        db = rtdb.reference()
        print("Firebase Realtime Database connected successfully!")
    else:
        print("Warning: No Firebase credentials found")
except Exception as e:
    print(f"Error initializing Firebase RTDB: {e}")

# Mock Database for drivers and their assigned trips
drivers_db = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manager/login')
def manager_login():
    return render_template('manager_login.html')

@app.route('/manager/dashboard')
def manager_dashboard():
    return render_template('manager_dashboard.html')

@app.route('/driver/login')
def driver_login():
    return render_template('driver_login.html')

@app.route('/driver/dashboard')
def driver_dashboard():
    if 'truck_number' not in session:
        return redirect(url_for('driver_login'))
    lang = session.get('language', 'en-US')
    return render_template('driver_dashboard.html', driver_lang=lang)

@app.route('/api/driver_login', methods=['POST'])
def api_driver_login():
    data = request.json
    name = data.get('name', '').strip()
    truck = data.get('truck_number', '').strip().upper()
    lang = data.get('language', 'en-US')
    
    try:
        if db:
            trip_data = db.child('trips').child(truck).get()
            if trip_data:
                if trip_data.get('driver_name', '').lower() == name.lower():
                    session['truck_number'] = truck
                    session['language'] = lang
                    return jsonify({'success': True})
    except Exception as e:
        print("Firebase Error (login):", e)
        
    if truck in drivers_db and drivers_db[truck]['driver_name'].lower() == name.lower():
        session['truck_number'] = truck
        session['language'] = lang
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid Driver Name or Truck Number. Make sure the manager has dispatched you!'})

@app.route('/api/dispatch_trip', methods=['POST'])
def dispatch_trip():
    data = request.json
    truck = data.get('truck_number', '').strip().upper()
    trip_data = {
        'driver_name': data.get('driver_name', '').strip(),
        'origin': data.get('origin', ''),
        'destination': data.get('destination', ''),
        'stoppage': data.get('stoppage', ''),
        'vehicle_size': data.get('vehicle_size', 'Standard Truck'),
        'product_expiry': data.get('product_expiry', 'No Limit'),
        'current_location': data.get('origin', ''), # Default to origin initially
        'status': 'Pending'
    }
    
    try:
        if db:
            db.child('trips').child(truck).set(trip_data)
    except Exception as e:
        print("Firebase Error (dispatch):", e)
        
    drivers_db[truck] = trip_data
    return jsonify({'success': True, 'message': 'Trip dispatched to driver successfully!'})

@app.route('/api/get_all_trips', methods=['GET'])
def get_all_trips():
    try:
        if db:
            trips = db.child('trips').get() or {}
            return jsonify({'success': True, 'trips': trips})
    except Exception as e:
        print("Firebase Error (get_all):", e)
        
    return jsonify({'success': True, 'trips': drivers_db})

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

@app.route('/api/update_location', methods=['POST'])
def update_location():
    truck = session.get('truck_number')
    if not truck:
        return jsonify({'success': False, 'error': 'Unauthorized'})
    data = request.json
    loc = data.get('location', '')
    dist_traveled = 0.0
    
    try:
        if db:
            trip_ref = db.child('trips').child(truck)
            trip_data = trip_ref.get() or {}
            old_loc = trip_data.get('current_location', '')
            dist_traveled = trip_data.get('distance_traveled_km', 0.0)
            
            if old_loc and old_loc != loc and ',' in old_loc and ',' in loc:
                try:
                    lat1, lon1 = map(float, old_loc.split(','))
                    lat2, lon2 = map(float, loc.split(','))
                    dist_traveled += haversine(lat1, lon1, lat2, lon2)
                except:
                    pass
                    
            trip_ref.update({
                'current_location': loc,
                'distance_traveled_km': round(dist_traveled, 2)
            })
    except Exception as e:
        print("Firebase Error (update_loc):", e)
        
    if truck in drivers_db:
        old_loc = drivers_db[truck].get('current_location', '')
        dist_traveled = drivers_db[truck].get('distance_traveled_km', 0.0)
        if old_loc and old_loc != loc and ',' in old_loc and ',' in loc:
            try:
                lat1, lon1 = map(float, old_loc.split(','))
                lat2, lon2 = map(float, loc.split(','))
                dist_traveled += haversine(lat1, lon1, lat2, lon2)
            except:
                pass
        drivers_db[truck]['current_location'] = loc
        drivers_db[truck]['distance_traveled_km'] = round(dist_traveled, 2)
        
    return jsonify({'success': True, 'distance_traveled_km': round(dist_traveled, 2)})

@app.route('/api/get_active_trip', methods=['GET'])
def get_active_trip():
    truck = request.args.get('truck_number') or session.get('truck_number')
    if truck:
        try:
            if db:
                trip_data = db.child('trips').child(truck).get()
                if trip_data:
                    return jsonify({'success': True, 'trip': trip_data})
        except Exception as e:
            print("Firebase Error (get_active):", e)
            
        if truck in drivers_db:
            return jsonify({'success': True, 'trip': drivers_db[truck]})
            
    return jsonify({'success': False, 'error': 'No active trip found.'})

@app.route('/api/update_status', methods=['POST'])
def update_status():
    truck = session.get('truck_number')
    if not truck:
        return jsonify({'success': False, 'error': 'Unauthorized'})
    data = request.json
    new_status = data.get('status', 'In Transit')
    
    import time
    update_payload = {'status': new_status}
    
    if new_status == 'In Transit':
        # Add start time only if not already present to avoid resetting on refresh
        try:
            if db:
                existing = db.child('trips').child(truck).get()
                if existing and not existing.get('start_time'):
                    update_payload['start_time'] = int(time.time() * 1000)
        except:
            update_payload['start_time'] = int(time.time() * 1000)
            
    try:
        if db:
            db.child('trips').child(truck).update(update_payload)
    except Exception as e:
        print("Firebase Error (update_status):", e)
        
    if truck in drivers_db:
        drivers_db[truck].update(update_payload)
    return jsonify({'success': True, 'start_time': update_payload.get('start_time')})

@app.route('/api/generate_route', methods=['POST'])
def generate_route():
    if not API_KEY:
        return jsonify({'success': False, 'error': 'Google Maps API Key not found in .env'})

    data = request.json
    origin = data.get('origin')
    destination = data.get('destination')
    
    def format_waypoint(wp):
        if isinstance(wp, dict) and 'lat' in wp and 'lng' in wp:
            return {"location": {"latLng": {"latitude": wp['lat'], "longitude": wp['lng']}}}
        
        wp_str = str(wp).strip()
        if ',' in wp_str:
            parts = wp_str.split(',')
            if len(parts) == 2:
                try:
                    lat, lng = float(parts[0].strip()), float(parts[1].strip())
                    return {"location": {"latLng": {"latitude": lat, "longitude": lng}}}
                except ValueError:
                    pass
        return {"address": wp_str}

    url = 'https://routes.googleapis.com/directions/v2:computeRoutes'
    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': API_KEY,
        'X-Goog-FieldMask': 'routes.polyline.encodedPolyline,routes.legs'
    }
    payload = {
        "origin": format_waypoint(origin),
        "destination": format_waypoint(destination),
        "travelMode": "DRIVE"
    }
    
    try:
        import requests
        response = requests.post(url, headers=headers, json=payload)
        resp_data = response.json()
        
        if 'error' in resp_data:
            return jsonify({'success': False, 'error': resp_data['error'].get('message', str(resp_data['error']))})
            
        routes = resp_data.get('routes')
        if not routes:
            return jsonify({'success': False, 'error': 'No route found'})
            
        route = routes[0]
        encoded_polyline = route['polyline']['encodedPolyline']
        coordinates = polyline.decode(encoded_polyline)
        
        start_location = route['legs'][0]['startLocation']['latLng']
        start_lat = start_location['latitude']
        start_lng = start_location['longitude']
        
        # Create Folium Map centered at start location
        m = folium.Map(location=[start_lat, start_lng], zoom_start=12)
        
        # Draw Polyline
        folium.PolyLine(locations=coordinates, color='#2563eb', weight=6).add_to(m)
        
        # Add Start/End Markers
        folium.Marker(location=coordinates[0], popup="Origin", icon=folium.Icon(color='green', icon='play')).add_to(m)
        folium.Marker(location=coordinates[-1], popup="Destination", icon=folium.Icon(color='red', icon='stop')).add_to(m)
        
        # Render HTML string
        map_html = m.get_root().render()
        return jsonify({'success': True, 'map_html': map_html})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/smart_route', methods=['POST'])
def smart_route():
    if not API_KEY:
        return jsonify({'success': False, 'error': 'Google Maps API Key not found'})

    data = request.json
    origin = data.get('origin')
    destination = data.get('destination')
    stoppage = data.get('stoppage')
    vehicle_size = data.get('vehicle_size', 'Standard Truck')
    expiry = data.get('product_expiry', 'No Limit')
    
    gemini_key = os.environ.get('GEMINI_API_KEY', '')

    def geocode_to_latlng(wp):
        # Convert user input to lat, lng using Google Geocoder for reliability
        if isinstance(wp, dict) and 'lat' in wp:
            return float(wp['lat']), float(wp['lng'])
        wp_str = str(wp).strip()
        if ',' in wp_str:
            try:
                parts = wp_str.split(',')
                return float(parts[0].strip()), float(parts[1].strip())
            except ValueError:
                pass
        import requests
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={wp_str}&key={API_KEY}"
        res = requests.get(url).json()
        if res.get('status') == 'OK':
            loc = res['results'][0]['geometry']['location']
            return loc['lat'], loc['lng']
        return None, None

    try:
        import requests
        import networkx as nx
        import osmnx as ox
        
        # 1. NetworkX A* Routing - Primary Route
        o_lat, o_lng = geocode_to_latlng(origin)
        d_lat, d_lng = geocode_to_latlng(destination)
        
        if o_lat is None or d_lat is None:
            return jsonify({'success': False, 'error': 'Could not geocode locations'})
            
        points_lat = [o_lat, d_lat]
        points_lng = [o_lng, d_lng]
        
        s_lat, s_lng = None, None
        if stoppage:
            s_lat, s_lng = geocode_to_latlng(stoppage)
            if s_lat is not None:
                points_lat.append(s_lat)
                points_lng.append(s_lng)
                
        min_lat, max_lat = min(points_lat), max(points_lat)
        min_lng, max_lng = min(points_lng), max(points_lng)
        center_lat = (min_lat + max_lat) / 2.0
        center_lng = (min_lng + max_lng) / 2.0
        
        engine_used = ""
        
        # Calculate radius in meters to determine the route length
        diag_km = haversine(min_lat, min_lng, max_lat, max_lng)
        
        if diag_km > 25:
            # HYBRID FALLBACK: For long routes, live downloading the street grid via NetworkX/OSMnx
            # takes too long and crashes the server. We fallback to the pre-compiled OSRM engine.
            engine_used = "OSRM (Fast Long-Distance)"
            
            coords_str = f"{o_lng},{o_lat}"
            if s_lat is not None:
                coords_str += f";{s_lng},{s_lat}"
            coords_str += f";{d_lng},{d_lat}"
            
            osrm_url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=polyline"
            osrm_res = requests.get(osrm_url).json()
            
            if osrm_res.get('code') != 'Ok':
                return jsonify({'success': False, 'error': 'OSRM Routing failed.'})
                
            primary_coords = polyline.decode(osrm_res['routes'][0]['geometry'])
            
            # Detour logic for OSRM
            has_obstruction = False
            # Check for incidents later, but placeholder here
            alt_coords = []
            
        else:
            # Use NetworkX A* for precise local routing
            engine_used = "NetworkX A* (Local Precision)"
            ox.settings.use_cache = True
            ox.settings.log_console = False
            
            kwargs = {'network_type': 'drive'}
                
            # Use a tight bounding box instead of a massive circular radius to drastically cut download times
            buffer = 0.02 # roughly 2km buffer around the route bounds
            bbox = (min_lng - buffer, min_lat - buffer, max_lng + buffer, max_lat + buffer)
            
            try:
                G = ox.graph_from_bbox(bbox=bbox, **kwargs)
            except TypeError:
                G = ox.graph_from_bbox(max_lat + buffer, min_lat - buffer, max_lng + buffer, min_lng - buffer, **kwargs)
            
            o_node = ox.distance.nearest_nodes(G, o_lng, o_lat)
            d_node = ox.distance.nearest_nodes(G, d_lng, d_lat)
            
            def heuristic(u, v):
                return haversine(G.nodes[u]['y'], G.nodes[u]['x'], G.nodes[v]['y'], G.nodes[v]['x']) * 1000
                
            primary_nodes = []
            if s_lat is not None:
                s_node = ox.distance.nearest_nodes(G, s_lng, s_lat)
                path1 = nx.astar_path(G, o_node, s_node, heuristic=heuristic, weight='length')
                path2 = nx.astar_path(G, s_node, d_node, heuristic=heuristic, weight='length')
                primary_nodes = path1[:-1] + path2
            else:
                primary_nodes = nx.astar_path(G, o_node, d_node, heuristic=heuristic, weight='length')
                
            primary_coords = [[G.nodes[n]['y'], G.nodes[n]['x']] for n in primary_nodes]
            alt_coords = []
            
        # Determine incident point (exactly 2.5 km ahead on the route)
        accumulated_dist = 0.0
        incident_coord = primary_coords[0] if primary_coords else [0, 0]
        incident_idx = 0
        for i in range(1, len(primary_coords)):
            lat1, lon1 = primary_coords[i-1]
            lat2, lon2 = primary_coords[i]
            accumulated_dist += haversine(lat1, lon1, lat2, lon2)
            if accumulated_dist >= 2.5:
                incident_coord = [lat2, lon2]
                incident_idx = i
                break
        
        # If route is super short, just use midpoint
        if accumulated_dist < 2.5 and len(primary_coords) > 2:
            incident_idx = len(primary_coords) // 2
            incident_coord = primary_coords[incident_idx]
            
        # Determine 5km Re-Routing Merge Point past the obstruction
        accumulated_dist_merge = 0.0
        merge_coord = None
        for i in range(incident_idx + 1, len(primary_coords)):
            lat1, lon1 = primary_coords[i-1]
            lat2, lon2 = primary_coords[i]
            accumulated_dist_merge += haversine(lat1, lon1, lat2, lon2)
            if accumulated_dist_merge >= 5.0:
                merge_coord = [lat2, lon2]
                break
        
        if not merge_coord:
            merge_coord = [d_lat, d_lng]

        # Integrate Open-Meteo Weather API & Live News API
        weather_alert = "Clear conditions."
        news_alert = "No major traffic incidents reported."
        weather_marker_lat = None
        weather_marker_lng = None
        news_key = os.environ.get('NEWS_API_KEY', '')
        
        # Check News API for accidents or traffic in the local current area
        try:
            if news_key:
                current_city = str(origin).split(',')[0] # Search near the driver
                n_url = f"https://newsapi.org/v2/everything?q={current_city}+traffic+OR+accident&sortBy=publishedAt&pageSize=1&apiKey={news_key}"
                n_res = requests.get(n_url).json()
                if n_res.get('status') == 'ok' and n_res.get('articles'):
                    news_alert = "ALERT: " + n_res['articles'][0]['title']
                else:
                    n_url2 = f"https://gnews.io/api/v4/search?q={current_city}+traffic+OR+accident&lang=en&max=1&apikey={news_key}"
                    n_res2 = requests.get(n_url2).json()
                    if 'articles' in n_res2 and len(n_res2['articles']) > 0:
                        news_alert = "ALERT: " + n_res2['articles'][0]['title']
        except Exception as e:
            print("News API error:", e)
        
        try:
            inc_lat, inc_lng = incident_coord
            w_url = f"https://api.open-meteo.com/v1/forecast?latitude={inc_lat}&longitude={inc_lng}&current_weather=true"
            w_res = requests.get(w_url).json()
            weather_code = w_res.get('current_weather', {}).get('weathercode', 0)
            
            if weather_code >= 61:
                weather_alert = f"Heavy Rain/Snow detected (Code {weather_code}) 2.5km ahead!"
                weather_marker_lat, weather_marker_lng = inc_lat, inc_lng
            else:
                weather_alert = f"Clear/Cloudy (Code {weather_code})"
        except Exception as e:
            print("Weather API error:", e)

        # 2. Detour Rerouting
        has_obstruction = weather_marker_lat or "ALERT" in news_alert
        if has_obstruction and len(primary_coords) > 2:
            if engine_used == "NetworkX A* (Local Precision)":
                # NetworkX A* Detour
                try:
                    inc_node = ox.distance.nearest_nodes(G, incident_coord[1], incident_coord[0])
                    G_detour = G.copy()
                    nodes_to_remove = [inc_node]
                    try:
                        nodes_to_remove.extend(list(G_detour.neighbors(inc_node)))
                    except nx.NetworkXError:
                        pass
                    G_detour.remove_nodes_from(nodes_to_remove)
                    if s_lat is not None:
                        alt_nodes = nx.astar_path(G_detour, o_node, d_node, heuristic=heuristic, weight='length')
                    else:
                        alt_nodes = nx.astar_path(G_detour, o_node, d_node, heuristic=heuristic, weight='length')
                    alt_coords = [[G_detour.nodes[n]['y'], G_detour.nodes[n]['x']] for n in alt_nodes]
                except nx.NetworkXNoPath:
                    pass
            else:
                # OSRM Detour
                detour_coords_str = f"{o_lng},{o_lat}"
                if s_lat is not None:
                    detour_coords_str += f";{s_lng},{s_lat}"
                detour_lat = incident_coord[0] + 0.025
                detour_lng = incident_coord[1] + 0.025
                detour_coords_str += f";{detour_lng},{detour_lat};{merge_coord[1]},{merge_coord[0]};{d_lng},{d_lat}"
                osrm_alt_url = f"http://router.project-osrm.org/route/v1/driving/{detour_coords_str}?overview=full&geometries=polyline"
                res2 = requests.get(osrm_alt_url).json()
                if res2.get('code') == 'Ok' and res2.get('routes'):
                    alt_coords = polyline.decode(res2['routes'][0]['geometry'])

        # 3. Gemini Analysis Integration
        gemini_analysis = ""
        if gemini_key:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            lang_pref = session.get('language', 'en-US')
            lang_str = "Respond ENTIRELY in Hindi language (हिंदी) using Devanagari script." if lang_pref == 'hi-IN' else "Respond in English."
            prompt = f"You are Optivion AI, a logistics assistant. The driver is driving a '{vehicle_size}'. Cargo expires in: '{expiry}'. Traveling from '{origin}' to '{destination}'. Weather alert: {weather_alert}. News alert: {news_alert}. We calculated an alternate route avoiding the obstruction. Give a brief, 2-sentence encouraging instruction to the driver explaining the route. {lang_str}"
            gemini_res = requests.post(gemini_url, json={"contents": [{"parts":[{"text": prompt}]}]})
            gemini_data = gemini_res.json()
            try:
                gemini_analysis = gemini_data['candidates'][0]['content']['parts'][0]['text']
            except:
                gemini_analysis = f"Gemini AI: Rerouting initiated to bypass obstructions. Your {vehicle_size} is on a safe path to meet the {expiry} deadline."
        else:
            gemini_analysis = f"<strong>[Gemini API Key Missing]</strong> Simulated AI: Heavy flooding ahead. I've recalculated a bypass route for your {vehicle_size} to ensure you deliver before the {expiry} expiry deadline."

        # 4. Map Generation
        start_lat, start_lng = primary_coords[0]
        m = folium.Map(location=[start_lat, start_lng], zoom_start=11)

        if has_obstruction:
            # Base path (Blue) but faded/dashed because it's blocked by construction/weather
            folium.PolyLine(locations=primary_coords, color='#3b82f6', weight=4, opacity=0.4, dash_array='10').add_to(m)
            # New Path / Detour (Green) suggested by AI
            if alt_coords:
                folium.PolyLine(locations=alt_coords, color='#10b981', weight=6, opacity=0.9).add_to(m)
        else:
            # Standard Base Path in Blue (No obstructions)
            folium.PolyLine(locations=primary_coords, color='#3b82f6', weight=6, opacity=0.9).add_to(m)
            
        # Standard route start/end Markers
        folium.Marker(location=primary_coords[0], popup="Start Route", icon=folium.Icon(color='blue')).add_to(m)
        folium.Marker(location=primary_coords[-1], popup="Destination", icon=folium.Icon(color='purple')).add_to(m)
        if "ALERT" in news_alert:
            folium.Marker(
                location=incident_coord, 
                popup=f"<b style='color:red;'>Obstruction!</b><br>{news_alert}", 
                icon=folium.Icon(color='red', icon='person-digging', prefix='fa')
            ).add_to(m)
        
        if weather_marker_lat:
            folium.Marker(
                location=[weather_marker_lat, weather_marker_lng], 
                popup=f"⚠️ Weather Obstruction: {weather_alert}", 
                icon=folium.Icon(color="darkred", icon="cloud-showers-heavy", prefix='fa')
            ).add_to(m)
        
        map_html = m.get_root().render()
        
        live_script = """
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                var mapObj = null;
                for (var key in window) {
                    if (key.startsWith('map_') && window[key] instanceof L.Map) {
                        mapObj = window[key];
                        break;
                    }
                }
                
                var liveMarker = null;
                var arrowIcon = L.divIcon({
                    html: '<div style="font-size: 28px; color: #3b82f6; filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.5)); transform: rotate(-45deg);"><i class="fa-solid fa-location-arrow"></i></div>',
                    className: 'live-arrow-icon',
                    iconSize: [28, 28],
                    iconAnchor: [14, 14]
                });

                window.updateLiveMarker = function(lat, lng) {
                    if (!mapObj) return;
                    var newLatLng = new L.LatLng(lat, lng);
                    if (!liveMarker) {
                        liveMarker = L.marker(newLatLng, {icon: arrowIcon, zIndexOffset: 1000}).addTo(mapObj);
                    } else {
                        liveMarker.setLatLng(newLatLng);
                    }
                    mapObj.flyTo(newLatLng, 15, { animate: true, duration: 1.5 });
                };
            });
        </script>
        """
        map_html = map_html.replace('</body>', live_script + '</body>')
        
        return jsonify({
            'success': True, 
            'map_html': map_html,
            'alerts': {
                'incident': news_alert,
                'weather': weather_alert
            },
            'gemini_analysis': gemini_analysis
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
