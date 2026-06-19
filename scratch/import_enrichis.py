import os
import csv

from stock.models import Medicament

def import_csv():
    csv_file = 'c:\\Users\\ASUS\\Desktop\\front-dev\\medicaments_enrichis.csv'
    if not os.path.exists(csv_file):
        print(f"File not found: {csv_file}")
        return

    updated_count = 0
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            nom = row['nom'].strip()
            description = row['description'].strip()
            
            # Find the medicament
            # Try exact match first
            meds = Medicament.objects.filter(nom__iexact=nom)
            if not meds.exists():
                # Try partial match
                first_word = nom.split()[0]
                meds = Medicament.objects.filter(nom__icontains=first_word)
            
            if meds.exists():
                for med in meds:
                    med.description = description
                    med.vecteur_semantique = None # Force recalculation
                    med.save()
                    updated_count += 1
                    print(f"Updated: {med.nom}")
            else:
                print(f"Not found in DB: {nom}")

    print(f"Total updated: {updated_count}")

import_csv()
