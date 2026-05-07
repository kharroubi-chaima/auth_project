import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_project.settings')
django.setup()

from pharmacies.models import Pharmacie

p = Pharmacie.objects.filter(proprietaire__email="admin.najeh@pharmacie.tn").first()
if p:
    print(f"Activating pharmacie: {p.nom}")
    p.est_active = True
    p.save()
    print("Done.")
else:
    print("Pharmacie not found for admin.najeh@pharmacie.tn")
