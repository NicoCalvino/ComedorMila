"""Los comprobantes del comedor pasan de ImageField a FileField para aceptar PDF.

No cambia la columna en la base (ambos son varchar con la ruta del archivo);
los comprobantes ya guardados siguen funcionando igual.
"""

import comedor.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comedor", "0014_solicitudpagocomedor_descripcion"),
    ]

    operations = [
        migrations.AlterField(
            model_name="valediario",
            name="comprobante",
            field=models.FileField(
                blank=True,
                default="default/noticket.png",
                null=True,
                upload_to=comedor.models.picture_upload_to,
                verbose_name="Picture",
            ),
        ),
        migrations.AlterField(
            model_name="solicitudpagocomedor",
            name="comprobante",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=comedor.models.comprobante_pago_comedor_upload_to,
            ),
        ),
    ]
