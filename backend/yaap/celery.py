"""Celery application configuration for YAAP."""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yaap.settings")

app = Celery("yaap")

# Load config from Django settings, namespace=CELERY
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
