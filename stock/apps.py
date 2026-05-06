# stock/apps.py  (fichier à créer ou modifier)
from django.apps import AppConfig
import os

class StockConfig(AppConfig):
    name = 'stock'

    def ready(self):
        if os.environ.get('SCHEDULER_STARTED'):
            return
        os.environ['SCHEDULER_STARTED'] = 'true'
        from .scheduler import start
        start()