from django.db import migrations
from django.db.models import OuterRef, Subquery


def forwards(apps, schema_editor):
    AuditEvent = apps.get_model('audit', 'AuditEvent')
    Organization = apps.get_model('accounts', 'Organization')
    User = apps.get_model('accounts', 'User')
    events = AuditEvent._base_manager
    events.filter(organization__isnull=False).update(
        organization_name=Subquery(
            Organization.objects.filter(pk=OuterRef('organization_id')).values('name')[
                :1
            ]
        )
    )
    subject_ids = events.filter(subject_user__isnull=False).values('subject_user_id')
    for user in User.objects.filter(pk__in=subject_ids).only(
        'email', 'first_name', 'last_name'
    ):
        name = ' '.join(filter(None, [user.first_name, user.last_name]))
        label = ' · '.join(filter(None, [user.email, name]))[:300]
        events.filter(subject_user_id=user.pk).update(subject_label=label)


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0005_audit_survives_deletes'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
