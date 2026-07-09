# Generated for careseeker onboarding resume state.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("careseekers", "0003_alter_careseeker_options_careseeker_created_by_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="careseeker",
            name="birth_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="careseeker",
            name="onboarding_resume",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
