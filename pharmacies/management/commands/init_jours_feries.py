from django.core.management.base import BaseCommand
from pharmacies.models import JourFerieTunisie


class Command(BaseCommand):
    help = 'Initialise les jours fériés tunisiens 2025 et 2026'

    JOURS_FERIES = [
        # ── 2025 ──────────────────────────────────────────
        ('2025-01-01', "Jour de l'An",           'fixe'),
        ('2025-01-14', "Fête de la Révolution",  'fixe'),
        ('2025-03-20', "Fête de l'Indépendance", 'fixe'),
        ('2025-03-30', "Aïd El Fitr J1",         'religieux'),
        ('2025-03-31', "Aïd El Fitr J2",         'religieux'),
        ('2025-05-01', "Fête du Travail",         'fixe'),
        ('2025-06-06', "Aïd El Adha J1",         'religieux'),
        ('2025-06-07', "Aïd El Adha J2",         'religieux'),
        ('2025-06-26', "Ras El Am El Hijri",      'religieux'),
        ('2025-07-25', "Fête de la République",  'fixe'),
        ('2025-08-13', "Fête de la Femme",       'fixe'),
        ('2025-09-04', "Mawlid El Nabawi",       'religieux'),
        ('2025-10-15', "Fête de l'Évacuation",   'fixe'),
        # ── 2026 ──────────────────────────────────────────
        ('2026-01-01', "Jour de l'An",           'fixe'),
        ('2026-01-14', "Fête de la Révolution",  'fixe'),
        ('2026-03-20', "Fête de l'Indépendance", 'fixe'),
        ('2026-03-20', "Aïd El Fitr J1",         'religieux'),
        ('2026-03-21', "Aïd El Fitr J2",         'religieux'),
        ('2026-05-01', "Fête du Travail",         'fixe'),
        ('2026-05-27', "Aïd El Adha J1",         'religieux'),
        ('2026-05-28', "Aïd El Adha J2",         'religieux'),
        ('2026-06-16', "Ras El Am El Hijri",      'religieux'),
        ('2026-07-25', "Fête de la République",  'fixe'),
        ('2026-08-13', "Fête de la Femme",       'fixe'),
        ('2026-08-25', "Mawlid El Nabawi",       'religieux'),
        ('2026-10-15', "Fête de l'Évacuation",   'fixe'),
    ]

    def handle(self, *args, **options):
        created_count  = 0
        existing_count = 0

        for date_str, nom, type_ferie in self.JOURS_FERIES:
            _, created = JourFerieTunisie.objects.get_or_create(
                date=date_str,
                nom=nom,
                defaults={'type_ferie': type_ferie}
            )
            if created:
                created_count += 1
                self.stdout.write(f'    {date_str} → {nom}')
            else:
                existing_count += 1
                self.stdout.write(f'     {date_str} → {nom} (existant)')

        self.stdout.write(self.style.SUCCESS(
            f'\n Jours fériés : {created_count} créés, {existing_count} déjà existants'
        ))