from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0011_invitation_status_data'),
    ]

    operations = [
        migrations.RemoveField(model_name='invitation', name='is_accepted'),
        migrations.RemoveField(model_name='invitation', name='is_declined'),
        migrations.RemoveField(model_name='invitation', name='is_expired'),
        migrations.AddConstraint(
            model_name='invitation',
            constraint=models.CheckConstraint(
                condition=~Q(status='accepted') | Q(accepted_at__isnull=False),
                name='invitation_accepted_has_date',
            ),
        ),
        migrations.AddConstraint(
            model_name='invitation',
            constraint=models.CheckConstraint(
                condition=~Q(status='declined') | Q(declined_at__isnull=False),
                name='invitation_declined_has_date',
            ),
        ),
    ]
