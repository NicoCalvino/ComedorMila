"""Medio de pago en las solicitudes de pago de comedor (transferencia / efectivo).

Las solicitudes existentes quedan como TRANSFERENCIA (el default), que es lo
único que se podía registrar hasta ahora.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comedor", "0012_movimientocomedor_cliente"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudpagocomedor",
            name="medio_pago",
            field=models.CharField(
                choices=[("TRANSFERENCIA", "Transferencia"), ("EFECTIVO", "Efectivo")],
                default="TRANSFERENCIA",
                max_length=15,
            ),
        ),
    ]
