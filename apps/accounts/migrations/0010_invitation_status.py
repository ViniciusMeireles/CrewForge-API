from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0009_email_upper_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('accepted', 'Accepted'),
                    ('declined', 'Declined'),
                    ('expired', 'Expired'),
                    ('revoked', 'Revoked'),
                ],
                db_index=True,
                default='pending',
                help_text='Lifecycle state of the invitation',
                max_length=16,
                verbose_name='Status',
            ),
        ),
    ]
