from django.core.management.base import BaseCommand
from pharmacies.models import Pharmacie, HoraireRamadan, PeriodeRamadan
from datetime import time, date


class Command(BaseCommand):
    help = 'Génère les horaires Ramadan officiels CNOPT pour toutes les pharmacies A'

    # Lun→Ven : 08h30→17h00 
    # Samedi  : 08h30→13h00
    # Dimanche: fermé
    HORAIRES_RAMADAN = {
        0: (time(8, 30), time(17, 0), None, None),  # Lundi
        1: (time(8, 30), time(17, 0), None, None),  # Mardi
        2: (time(8, 30), time(17, 0), None, None),  # Mercredi
        3: (time(8, 30), time(17, 0), None, None),  # Jeudi
        4: (time(8, 30), time(17, 0), None, None),  # Vendredi
        5: (time(8, 30), time(13, 0), None, None),  # Samedi
        6: (None,        None,        None, None),  # Dimanche fermé
    }

    def handle(self, *args, **options):
        periode = PeriodeRamadan.objects.filter(
            date_debut__lte=date.today(),
            date_fin__gte=date.today()
        ).first()

        if not periode:
            self.stdout.write(self.style.WARNING('⚠️  Aucune période Ramadan active'))
            return

        self.stdout.write(f'🌙 Période trouvée : {periode}')

        pharmacies    = Pharmacie.objects.filter(categorie='A', est_active=True)
        created_count = 0
        updated_count = 0

        for pharmacie in pharmacies:
            for jour, (h1d, h1f, h2d, h2f) in self.HORAIRES_RAMADAN.items():
                obj, created = HoraireRamadan.objects.get_or_create(
                    pharmacie=pharmacie,
                    jour=jour,
                    defaults={
                        'est_ouvert':        h1d is not None,
                        'heure_ouverture_1': h1d,
                        'heure_fermeture_1': h1f,
                        'heure_ouverture_2': h2d,
                        'heure_fermeture_2': h2f,
                    }
                )
                if created:
                    created_count += 1
                else:
                    # Mettre à jour si déjà existant (anciens horaires incorrects)
                    obj.est_ouvert        = h1d is not None
                    obj.heure_ouverture_1 = h1d
                    obj.heure_fermeture_1 = h1f
                    obj.heure_ouverture_2 = h2d
                    obj.heure_fermeture_2 = h2f
                    obj.save()
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Horaires Ramadan CNOPT appliqués !\n'
            f'   → {pharmacies.count()} pharmacies A traitées\n'
            f'   → {created_count} créés, {updated_count} mis à jour\n'
            f'   → Lun→Ven : 08h30→17h00\n'
            f'   → Samedi  : 08h30→13h00\n'
            f'   → Dimanche: fermé\n'
        ))