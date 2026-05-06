from django.core.management.base import BaseCommand
 
 
class Command(BaseCommand):
    help = "Envoie des notifications WebSocket pour les médicaments qui expirent bientôt."
 
    def add_arguments(self, parser):
        parser.add_argument(
            '--jours',
            type=int,
            default=30,
            help='Nombre de jours avant expiration (défaut : 30)',
        )
 
    def handle(self, *args, **options):
        # Délègue à sms_service qui gère :
        #   - la récupération des stocks concernés
        #   - le filtre anti-doublon (< 24h)
        #   - l'envoi via WebSocket
        #   - la sauvegarde en base de données
        from stock.sms_service import notifier_expirations_proches  # ← ajustez l'app name
 
        jours = options['jours']
 
        self.stdout.write(
            f"Recherche des médicaments expirant dans les {jours} prochains jours..."
        )
 
        total = notifier_expirations_proches(jours=jours)
 
        self.stdout.write(
            self.style.SUCCESS(f"\n{total} notification(s) envoyée(s) avec succès.")
        )