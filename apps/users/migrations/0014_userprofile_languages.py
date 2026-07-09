from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_userprofile_ethnicity"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="languages",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
