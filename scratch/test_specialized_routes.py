import urllib.request
import urllib.parse
import json
import time

BASE = 'http://127.0.0.1:8000'

# Login
payload = json.dumps({
    'email': 'superadmin@gestionpharmacie.tn',
    'password': 'SuperAdmin@2026!'
}).encode('utf-8')

req = urllib.request.Request(
    f'{BASE}/api/auth/login/',
    data=payload,
    headers={'Content-Type': 'application/json'}
)

with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode('utf-8')).get('access')

print(f"Token OK\n")

queries = ['mal de tete', 'fievre', 'brulure peau', 'grippe']

for q in queries:
    q_encoded = urllib.parse.quote(q)
    url = f'{BASE}/api/reservations/recherche/?mode=symptome&medicament={q_encoded}&lat=36.8065&lng=10.1815&rayon=10'
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    })
    
    t0 = time.time()
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    dt = time.time() - t0
    
    print(f"=== '{q}' === ({dt:.3f}s, {len(data)} results)")
    for r in data[:8]:
        print(f"  - {r['medicament_nom']} | score: {r.get('score_pertinence', 0):.4f}")
    print()
