from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_user_email_verification_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="phone_verification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
