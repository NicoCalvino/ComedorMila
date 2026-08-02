# Generated for productos: picture ahora opcional (blank=True)

import productos.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('productos', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='picture',
            field=models.ImageField(blank=True, upload_to=productos.models.picture_upload_to, verbose_name='Picture'),
        ),
    ]
