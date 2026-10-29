from django.db import migrations
from django.db.models import OuterRef, Subquery, Value
from django.db.models.functions import Coalesce, Concat, Trim


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
    label = Trim(
        Concat(
            'email',
            Value(' · '),
            Coalesce('first_name', Value('')),
            Value(' '),
            Coalesce('last_name', Value('')),
        )
    )
    events.filter(subject_user__isnull=False).update(
        subject_label=Subquery(
            User.objects.filter(pk=OuterRef('subject_user_id'))
            .annotate(label=label)
            .values('label')[:1]
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0005_audit_survives_deletes'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
