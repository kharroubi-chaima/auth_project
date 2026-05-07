import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_project.settings')
django.setup()

from pharmacies.models import Pharmacie
from django.contrib.auth import get_user_model

User = get_user_model()

print("--- USERS ---")
for u in User.objects.all():
    print(f"User: {u.email}, ID: {u.id}, is_staff: {u.is_staff}")

print("\n--- PHARMACIES ---")
for p in Pharmacie.objects.all():
    print(f"Pharmacie: {p.nom}, Owner: {p.proprietaire.email if p.proprietaire else 'NONE'}, Active: {p.est_active}")
    print(f"  Employees: {[u.email for u in p.pharmaciens_travail.all()] if hasattr(p, 'pharmaciens_travail') else 'N/A'}")
