from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PlatformConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platform'
    verbose_name = _('Platform')
