from django.core.management.base import BaseCommand
from pharmacies.models import PeriodeRamadan


class Command(BaseCommand):
    help = 'Initialise les périodes de Ramadan'

    PERIODES = [
        (2025, '2025-03-01', '2025-03-29'),
        (2026, '2026-02-18', '2026-03-19'),
        (2027, '2027-02-07', '2027-03-08'),
    ]

    def handle(self, *args, **options):
        created_count  = 0
        existing_count = 0

        for annee, debut, fin in self.PERIODES:
            _, created = PeriodeRamadan.objects.get_or_create(
                annee=annee,
                defaults={'date_debut': debut, 'date_fin': fin}
            )
            if created:
                created_count += 1
                self.stdout.write(f'    Ramadan {annee} : {debut} → {fin}')
            else:
                existing_count += 1
                self.stdout.write(f'     Ramadan {annee} (existant)')

        self.stdout.write(self.style.SUCCESS(
            f'\n Ramadan : {created_count} créés, {existing_count} déjà existants'
        ))
        