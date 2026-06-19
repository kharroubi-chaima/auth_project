import os
import django

# Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth_project.settings')
django.setup()

from stock.models import Medicament, StockPharmacie, MouvementStock, LigneVente, Notification
from reservations.models import Reservation
from django.db.models import Count
from django.db import transaction

@transaction.atomic
def merge_all_duplicates():
    print("--- DÉBUT DE LA FUSION DES DOUBLONS ---")
    
    # 1. Identifier les groupes de doublons (Nom + DCI)
    dups = Medicament.objects.values('nom', 'dci').annotate(count=Count('id')).filter(count__gt=1)
    
    total_merged = 0
    
    for group in dups:
        nom = group['nom']
        dci = group['dci']
        
        # Récupérer tous les médicaments correspondants, triés par ID (le plus vieux devient le master)
        meds = list(Medicament.objects.filter(nom=nom, dci=dci).order_by('id'))
        master = meds[0]
        duplicates = meds[1:]
        
        print(f"\nFusion de {len(duplicates)} doublons vers le Master ID {master.id} ({master.nom})")
        
        for dup in duplicates:
            # A. Gérer les stocks (StockPharmacie)
            stocks_dup = StockPharmacie.objects.filter(medicament=dup)
            for sd in stocks_dup:
                # Vérifier si le master a déjà un stock dans cette pharmacie
                ms = StockPharmacie.objects.filter(pharmacie=sd.pharmacie, medicament=master).first()
                if ms:
                    # Fusionner les quantités
                    print(f"  - Fusion stock pharmacie {sd.pharmacie.id}: {sd.quantite_stock} unités ajoutées au Master stock {ms.id}")
                    ms.quantite_stock += sd.quantite_stock
                    ms.save()
                    
                    # Réaffecter les mouvements et réservations liés à ce stock
                    MouvementStock.objects.filter(stock=sd).update(stock=ms)
                    Reservation.objects.filter(stock=sd).update(stock=ms)
                    
                    # Supprimer le stock doublon
                    sd.delete()
                else:
                    # Réaffecter simplement le stock au médicament master
                    sd.medicament = master
                    sd.save()
            
            # B. Réaffecter les autres relations directes avec Medicament
            LigneVente.objects.filter(medicament=dup).update(medicament=master)
            Notification.objects.filter(medicament=dup).update(medicament=master)
            Reservation.objects.filter(medicament=dup).update(medicament=master)
            
            # C. Supprimer le médicament doublon
            print(f"  - Suppression du médicament doublon ID {dup.id}")
            dup.delete()
            total_merged += 1

    print(f"\n--- FUSION TERMINÉE : {total_merged} doublons supprimés ---")

if __name__ == '__main__':
    merge_all_duplicates()
