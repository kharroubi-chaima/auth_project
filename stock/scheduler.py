from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command

def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: call_command('envoyer_alertes_expiration'),
        'cron',
        hour=8,
        minute=0,
    )
    scheduler.start()