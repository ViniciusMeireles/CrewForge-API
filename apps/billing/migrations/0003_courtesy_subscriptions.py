from django.db import migrations

from apps.billing.backfill import create_courtesy_subscriptions


def forwards(apps, schema_editor):
    create_courtesy_subscriptions(
        apps.get_model('accounts', 'Organization'),
        apps.get_model('billing', 'Subscription'),
        apps.get_model('billing', 'Plan'),
    )


def backwards(apps, schema_editor):
    apps.get_model('billing', 'Subscription').objects.filter(
        courtesy='legacy'
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('billing', '0002_seed_plans'),
        ('accounts', '0018_user_token_version'),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
