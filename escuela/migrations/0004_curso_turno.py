"""Turno (hora de almuerzo) de cada curso. Opcional."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("escuela", "0003_cliente_limite"),
    ]

    operations = [
        migrations.AddField(
            model_name="curso",
            name="turno",
            field=models.TimeField(blank=True, null=True),
        ),
    ]
