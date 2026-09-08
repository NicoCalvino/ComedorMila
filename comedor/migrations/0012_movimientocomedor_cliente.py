"""Cargo mensual con detalle por hijo.

Agrega ``MovimientoComedor.cliente`` y cambia la unicidad del cargo mensual de
(cuenta, período) a (cuenta, período, hijo), para poder volver a generar un mes
y cobrarle solo a los hijos que todavía no tienen cargo.

Los cargos ya emitidos quedan con cliente = NULL, salvo los de las familias con
un único plan mensual: en ese caso no hay ambigüedad y se les atribuye ese hijo.
Los cargos viejos de familias con varios hijos se regularizan desde el control
de desvíos de "Generar cargos del mes".
"""

from django.db import migrations, models
import django.db.models.deletion


def atribuir_cargos_de_hijo_unico(apps, schema_editor):
    MovimientoComedor = apps.get_model("comedor", "MovimientoComedor")
    ValeMensual = apps.get_model("comedor", "ValeMensual")

    cargos = (
        MovimientoComedor.objects
        .filter(tipo="CARGO_MENSUAL", cliente__isnull=True)
        .select_related("cuenta")
    )
    for cargo in cargos:
        planes = list(
            ValeMensual.objects.filter(usuario_id=cargo.cuenta.usuario_id)[:2]
        )
        if len(planes) == 1:
            cargo.cliente_id = planes[0].cliente_id
            cargo.save(update_fields=["cliente"])


def revertir(apps, schema_editor):
    # No hace falta deshacer la atribución: el campo se elimina igual.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("comedor", "0011_alter_inasistencia_resultado"),
        ("escuela", "0003_cliente_limite"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimientocomedor",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="movimientos_comedor",
                to="escuela.cliente",
            ),
        ),
        migrations.AlterField(
            model_name="movimientocomedor",
            name="periodo",
            field=models.CharField(
                blank=True,
                help_text="AAAA-MM (cargos mensuales y ajustes de un mes).",
                max_length=7,
                null=True,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="movimientocomedor",
            name="unico_cargo_mensual_por_periodo",
        ),
        migrations.AddConstraint(
            model_name="movimientocomedor",
            constraint=models.UniqueConstraint(
                condition=models.Q(("tipo", "CARGO_MENSUAL")),
                fields=("cuenta", "periodo", "cliente"),
                name="unico_cargo_mensual_por_periodo_hijo",
            ),
        ),
        migrations.RunPython(atribuir_cargos_de_hijo_unico, revertir),
    ]
