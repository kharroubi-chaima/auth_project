# pharmacies/management/commands/generer_gardes.py
from django.core.management.base import BaseCommand
from pharmacies.models import Pharmacie, GardePharmacie
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Génère automatiquement les gardes par roulement'

    def add_arguments(self, parser):
        parser.add_argument('--mois', type=int, default=date.today().month)
        parser.add_argument('--annee', type=int, default=date.today().year)

    def handle(self, *args, **options):
        mois  = options['mois']
        annee = options['annee']

        # Récupère toutes les pharmacies actives par délégation
        from localisations.models import Delegation
        delegations = Delegation.objects.all()

        for delegation in delegations:
            pharmacies_A = list(Pharmacie.objects.filter(
                delegation=delegation,
                categorie='A',
                est_active=True
            ))
            pharmacies_B = list(Pharmacie.objects.filter(
                delegation=delegation,
                categorie='B',
                est_active=True
            ))

            if not pharmacies_A and not pharmacies_B:
                continue

            # Générer pour chaque jour du mois
            debut_mois = date(annee, mois, 1)
            if mois == 12:
                fin_mois = date(annee + 1, 1, 1) - timedelta(days=1)
            else:
                fin_mois = date(annee, mois + 1, 1) - timedelta(days=1)

            jour_courant = debut_mois
            index_A = 0
            index_B = 0

            while jour_courant <= fin_mois:
                jour_semaine = jour_courant.weekday()

                # Dimanche → pharmacie A de garde
                if jour_semaine == 6 and pharmacies_A:
                    pharmacie = pharmacies_A[index_A % len(pharmacies_A)]
                    GardePharmacie.objects.get_or_create(
                        pharmacie=pharmacie,
                        date_debut=jour_courant,
                        date_fin=jour_courant,
                        defaults={'type_garde': 'dimanche'}
                    )
                    index_A += 1

                # Chaque nuit → TOUTES les pharmacies B de garde
                if pharmacies_B:
                    for pharmacie_B in pharmacies_B:
                        GardePharmacie.objects.get_or_create(
                            pharmacie=pharmacie_B,
                            date_debut=jour_courant,
                            date_fin=jour_courant,
                            defaults={'type_garde': 'nuit'}
                        )

                jour_courant += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(' Gardes générées avec succès !'))