# accounts/apps.py
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        import os
        # Évite le double appel du StatReloader
        if os.environ.get('RUN_MAIN') != 'true':
            return
        import threading
        def warmup():
            from .views import get_deepface
            get_deepface()
            print("✅ DeepFace warmup terminé.")
        threading.Thread(target=warmup, daemon=True).start()