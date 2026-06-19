import urllib.request
import json
import time

url_login = 'http://127.0.0.1:8000/api/auth/login/'
url_search = 'http://127.0.0.1:8000/api/reservations/recherche/?mode=symptome&medicament=grippe&lat=36.8065&lng=10.1815&rayon=10'

# Login payload
payload = json.dumps({
    'email': 'superadmin@gestionpharmacie.tn',
    'password': 'SuperAdmin@2026!'
}).encode('utf-8')

# Login request
req_login = urllib.request.Request(
    url_login,
    data=payload,
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req_login) as response:
        login_data = json.loads(response.read().decode('utf-8'))
        token = login_data.get('access') or login_data.get('token')
        print("Logged in successfully. Token obtained.")
        
        # Search request
        req_search = urllib.request.Request(
            url_search,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
        )
        
        start_time = time.time()
        with urllib.request.urlopen(req_search) as search_res:
            results = json.loads(search_res.read().decode('utf-8'))
            duration = time.time() - start_time
            print(f"Request to running Django server took: {duration:.4f} seconds")
            print(f"Number of results returned: {len(results)}")
            if results:
                print(f"First result: {results[0]['medicament_nom']} (pertinence: {results[0].get('score_pertinence')})")
except Exception as e:
    print(f"Error making request to running Django server: {e}")
