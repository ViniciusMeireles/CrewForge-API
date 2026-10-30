import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

app = Celery('crew_forge')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
