from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_remove_userprofile_preferred_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="ethnicity",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
