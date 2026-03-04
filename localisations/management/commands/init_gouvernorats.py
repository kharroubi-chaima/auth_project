from django.core.management.base import BaseCommand
from localisations.models import Gouvernorat


class Command(BaseCommand):
    help = 'Initialise les 24 gouvernorats tunisiens'

    GOUVERNORATS = [
        "Tunis", "Ariana", "Ben Arous", "Manouba",
        "Nabeul", "Zaghouan", "Bizerte", "Béja",
        "Jendouba", "Kef", "Siliana", "Sousse",
        "Monastir", "Mahdia", "Sfax", "Kairouan",
        "Kasserine", "Sidi Bouzid", "Gabès", "Médenine",
        "Tataouine", "Gafsa", "Tozeur", "Kébili"
    ]

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0

        for nom in self.GOUVERNORATS:
            _, created = Gouvernorat.objects.get_or_create(nom=nom)
            if created:
                created_count += 1
                self.stdout.write(f' {nom}')
            else:
                existing_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n Gouvernorats : {created_count} créés, {existing_count} déjà existants'
        ))