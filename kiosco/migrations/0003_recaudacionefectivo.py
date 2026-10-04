"""Recaudación diaria en efectivo del kiosco (la carga el admin)."""

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("kiosco", "0002_alter_tarjeta_codigo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RecaudacionEfectivo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha", models.DateField(error_messages={"unique": "Ya hay una recaudación cargada para esa fecha."}, unique=True)),
                ("monto", models.DecimalField(decimal_places=2, max_digits=10, validators=[
                    django.core.validators.MinValueValidator(Decimal("0.01")),
                    django.core.validators.MaxValueValidator(Decimal("99999999.99")),
                ])),
                ("observaciones", models.CharField(blank=True, default="", max_length=200)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("modificado", models.DateTimeField(auto_now=True)),
                ("cargado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Recaudación en efectivo",
                "verbose_name_plural": "Recaudaciones en efectivo",
                "ordering": ["-fecha"],
            },
        ),
    ]
