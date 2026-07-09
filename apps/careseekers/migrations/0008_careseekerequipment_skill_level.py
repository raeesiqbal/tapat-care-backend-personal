from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("careseekers", "0007_alter_careseekercondition_condition_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="careseekerequipment",
            name="skill_level",
            field=models.CharField(
                choices=[
                    ("no_experience", "No experience"),
                    ("some_experience", "Some experience"),
                    ("good_experience", "Good experience"),
                    ("excellent_experience", "Excellent experience"),
                ],
                default="no_experience",
                max_length=32,
            ),
            preserve_default=False,
        ),
    ]
