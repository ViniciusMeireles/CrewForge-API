import uuid

from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Upper


def forwards(apps, schema_editor):
    Invitation = apps.get_model('accounts', 'Invitation')
    duplicate_keys = (
        Invitation.objects.values('key').annotate(n=Count('id')).filter(n__gt=1)
    )
    for row in duplicate_keys:
        for invitation in Invitation.objects.filter(key=row['key']).order_by('id')[1:]:
            invitation.key = uuid.uuid4()
            invitation.save(update_fields=['key'])
    pending = Invitation.objects.filter(status='pending').annotate(
        email_upper=Upper('email')
    )
    groups = (
        pending.values('organization_id', 'email_upper')
        .annotate(n=Count('id'))
        .filter(n__gt=1)
    )
    for group in groups:
        stale = pending.filter(
            organization_id=group['organization_id'],
            email_upper=group['email_upper'],
        ).order_by('-id')[1:]
        Invitation.objects.filter(pk__in=[i.pk for i in stale]).update(
            status='revoked', is_active=False
        )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0012_invitation_status_constraints'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
