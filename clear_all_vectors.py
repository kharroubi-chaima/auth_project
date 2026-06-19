import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_project.settings')
django.setup()

from stock.models import Medicament

def clear_vectors():
    meds = Medicament.objects.all()
    count = 0
    for med in meds:
        if med.vecteur_semantique is not None:
            med.vecteur_semantique = None
            med.save(update_fields=['vecteur_semantique'])
            count += 1
    print(f"Cleared vectors for {count} medications.")

if __name__ == '__main__':
    clear_vectors()
