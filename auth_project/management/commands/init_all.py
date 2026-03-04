# auth_project/management/commands/init_all.py
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Initialise toutes les données de base du projet'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            '\n🚀 Initialisation complète du projet...\n'
        ))

        etapes = [
            ('init_admin',        '👤 Permissions, Rôles & Administrateur'),
            ('init_gouvernorats', '🗺️  Gouvernorats tunisiens'),
            ('init_delegations',  '📍 Délégations tunisiennes'),
            ('init_jours_feries', '📅 Jours fériés'),
            ('init_ramadan',      '🌙 Périodes Ramadan'),
        ]

        for command, label in etapes:
            self.stdout.write(f'\n{label}...')
            try:
                call_command(command)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Erreur : {e}'))
                continue

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Initialisation complète terminée !\n'
        ))