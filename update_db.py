import os
import django
import csv

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_project.settings')
django.setup()

from stock.models import Medicament

def update_descriptions():
    csv_file_path = r'c:\Users\ASUS\Desktop\front-dev\medicaments_enrichis.csv'
    updated_count = 0
    not_found_count = 0
    with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            nom = row['nom']
            desc = row['description']
            meds = Medicament.objects.filter(nom__iexact=nom)
            if meds.exists():
                for med in meds:
                    med.description = desc
                    med.vecteur_semantique = None
                    med.save(update_fields=['description', 'vecteur_semantique'])
                    print(f"Updated: {nom}")
                    updated_count += 1
            else:
                print(f"Not found: {nom}")
                not_found_count += 1
                
    print(f"\nSummary: {updated_count} updated, {not_found_count} not found.")

if __name__ == '__main__':
    update_descriptions()
