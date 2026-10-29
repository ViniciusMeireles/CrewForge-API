from django.db import migrations


def forwards(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    OrganizationProfile = apps.get_model('accounts', 'OrganizationProfile')
    missing = Organization.objects.filter(profile__isnull=True)
    OrganizationProfile.objects.bulk_create(
        [OrganizationProfile(organization=organization) for organization in missing]
    )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0016_single_owner'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
