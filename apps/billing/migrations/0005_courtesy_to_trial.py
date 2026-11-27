from django.db import migrations
from django.utils import timezone

from apps.billing.backfill import (
    convert_legacy_courtesy_to_trial,
    restore_legacy_courtesy,
)


def forwards(apps, schema_editor):
    convert_legacy_courtesy_to_trial(
        apps.get_model('billing', 'Subscription'),
        apps.get_model('billing', 'Plan'),
        timezone.now(),
    )


def backwards(apps, schema_editor):
    restore_legacy_courtesy(apps.get_model('billing', 'Subscription'))


class Migration(migrations.Migration):
    dependencies = [('billing', '0004_payments')]

    operations = [migrations.RunPython(forwards, backwards)]
