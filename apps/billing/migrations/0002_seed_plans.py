from django.db import migrations

from apps.billing.backfill import remove_seed_plans, seed_plans


def forwards(apps, schema_editor):
    seed_plans(apps.get_model('billing', 'Plan'))


def backwards(apps, schema_editor):
    remove_seed_plans(apps.get_model('billing', 'Plan'))


class Migration(migrations.Migration):
    dependencies = [('billing', '0001_initial')]

    operations = [migrations.RunPython(forwards, backwards)]
