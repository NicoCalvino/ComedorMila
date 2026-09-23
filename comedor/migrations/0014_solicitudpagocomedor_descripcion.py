"""Descripción libre en las solicitudes de pago de comedor (la carga el admin)."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comedor", "0013_solicitudpagocomedor_medio_pago"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudpagocomedor",
            name="descripcion",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
