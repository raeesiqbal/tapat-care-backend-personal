from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0013_user_stripe_customer_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="email_verification_nonce",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="email_verification_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
