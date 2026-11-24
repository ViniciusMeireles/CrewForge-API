from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


def ensure_seed_plans(sender, apps=None, **kwargs):
    from django.apps import apps as global_apps

    from apps.billing.backfill import seed_plans

    try:
        plan_model = (apps or global_apps).get_model('billing', 'Plan')
    except LookupError:
        return
    seed_plans(plan_model)


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.billing'
    verbose_name = _('Billing')

    def ready(self):
        post_migrate.connect(ensure_seed_plans, sender=self)
