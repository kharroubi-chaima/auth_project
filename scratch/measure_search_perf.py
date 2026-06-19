import os
import sys
import time

# Set up Django environment
sys.path.append(r'c:\Users\ASUS\Desktop\front-dev\auth_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_project.settings')

import django
django.setup()

from stock.semantic_search import SemanticSearchService
from reservations.views import RecherchePharmacieView
from rest_framework.test import APIRequestFactory, force_authenticate
from accounts.models import User

# Test Semantic Search directly
print("Testing direct semantic search...")
start_time = time.time()
results = SemanticSearchService.search("grippe et fievre", top_k=8)
duration = time.time() - start_time
print(f"Direct semantic search took: {duration:.4f} seconds")
print(f"Results: {len(results)}")
for r in results:
    print(f" - {r['medicament'].nom} (Score: {r['score']:.4f})")

# Test RecherchePharmacieView (symptome mode)
print("\nTesting RecherchePharmacieView (symptome mode)...")
user = User.objects.filter(is_active=True).first()
if user:
    factory = APIRequestFactory()
    request = factory.get('/api/reservations/recherche/', {
        'mode': 'symptome',
        'medicament': 'grippe et fievre',
        'lat': '36.8065',
        'lng': '10.1815',
        'rayon': '10'
    })
    force_authenticate(request, user=user)
    
    view = RecherchePharmacieView.as_view()
    start_time = time.time()
    response = view(request)
    duration = time.time() - start_time
    print(f"RecherchePharmacieView took: {duration:.4f} seconds")
    print(f"Status code: {response.status_code}")
    print(f"Response size: {len(response.data) if response.status_code == 200 else response.data}")
else:
    print("No active user found to test the view.")
