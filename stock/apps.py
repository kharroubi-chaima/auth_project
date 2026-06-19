# stock/apps.py
from django.apps import AppConfig
import os


class StockConfig(AppConfig):
    name = 'stock'

    def ready(self):
        import threading

        def preload():
            try:
                # Etape 1 : charger le modèle IA (lourd, ~500 Mo)
                from .semantic_search import SemanticSearchService
                model = SemanticSearchService.get_model()
                print("[SemanticSearch] Modele SentenceTransformer precharge.")

                # Etape 2 : construire la matrice d'embeddings en mémoire
                SemanticSearchService._build_matrix(model)
                print("[SemanticSearch] Matrice d'embeddings prechargee en memoire.")
            except Exception as e:
                print(f"[SemanticSearch] Erreur prechargement semantique : {e}")

        threading.Thread(target=preload, daemon=True).start()

        # Démarrage du scheduler (une seule fois)
        if os.environ.get('SCHEDULER_STARTED'):
            return
        os.environ['SCHEDULER_STARTED'] = 'true'
        from .scheduler import start
        start()