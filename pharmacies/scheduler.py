from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command
from datetime import date

def generer_gardes_auto():
    aujourd_hui = date.today()
    call_command('generer_gardes', mois=aujourd_hui.month, annee=aujourd_hui.year)

def start():
    scheduler = BackgroundScheduler()
    
    # 1er de chaque mois à 00h01
    scheduler.add_job(
        generer_gardes_auto,
        trigger='cron',
        day=1,
        hour=0,
        minute=1,
        id='generer_gardes',
        replace_existing=True
    )
    
    scheduler.start()
    