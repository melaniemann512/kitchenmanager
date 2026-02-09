"""
WSGI config for homeapp project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "homeapp.settings")

application = get_wsgi_application()
