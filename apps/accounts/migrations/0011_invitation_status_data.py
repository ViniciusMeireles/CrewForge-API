from django.db import migrations, models


def forwards(apps, schema_editor):
    Invitation = apps.get_model('accounts', 'Invitation')
    Invitation.objects.filter(is_active=False).update(status='revoked')
    active = Invitation.objects.filter(is_active=True)
    active.filter(is_accepted=True).update(status='accepted')
    active.filter(is_accepted=True, accepted_at__isnull=True).update(
        accepted_at=models.F('updated_at')
    )
    undecided = active.filter(is_accepted=False)
    undecided.filter(is_declined=True).update(status='declined')
    undecided.filter(is_declined=True, declined_at__isnull=True).update(
        declined_at=models.F('updated_at')
    )
    undecided.filter(is_declined=False, is_expired=True).update(status='expired')


def backwards(apps, schema_editor):
    Invitation = apps.get_model('accounts', 'Invitation')
    Invitation.objects.filter(status='accepted').update(is_accepted=True)
    Invitation.objects.filter(status='declined').update(is_declined=True)
    Invitation.objects.filter(status='expired').update(is_expired=True)
    Invitation.objects.filter(status='revoked').update(is_active=False)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0010_invitation_status'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
