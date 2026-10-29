from django.db import migrations


def forwards(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    Member = apps.get_model('accounts', 'Member')
    Invitation = apps.get_model('accounts', 'Invitation')
    Invitation.objects.filter(status='pending', role='owner').update(role='admin')
    problems = []
    for organization in Organization.objects.all().iterator():
        owners = Member.objects.filter(
            organization=organization, role='owner', is_active=True
        )
        chosen = None
        if organization.owner_id:
            chosen = Member.objects.filter(
                pk=organization.owner_id, organization=organization, is_active=True
            ).first()
        if chosen is None:
            if owners.count() > 1:
                problems.append(f'{organization.pk} ({owners.count()} active owners)')
            continue
        owners.exclude(pk=chosen.pk).update(role='admin')
        if chosen.role != 'owner':
            chosen.role = 'owner'
            chosen.save(update_fields=['role'])
    if problems:
        raise RuntimeError(
            'Organizations without a resolvable single owner: ' + ', '.join(problems)
        )


def backwards(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    Member = apps.get_model('accounts', 'Member')
    for member in Member.objects.filter(role='owner', is_active=True):
        Organization.objects.filter(pk=member.organization_id).update(owner=member)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0014_invitation_uniqueness'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
