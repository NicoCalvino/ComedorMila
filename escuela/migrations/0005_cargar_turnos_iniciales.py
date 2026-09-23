"""Carga inicial de turnos (hora de almuerzo) por curso.

- Jardín: 12:25
- Primaria 1° a 3° grado: 12:30
- Primaria 4° a 7° grado: 13:00
- Secundaria: 13:30

Solo completa cursos que todavía no tienen turno, así que no pisa horarios
cargados a mano. El grado de primaria se toma del primer número del nombre del
curso ("1° Grado A" -> 1).
"""

import re
from datetime import time

from django.db import migrations


def cargar_turnos(apps, schema_editor):
    Curso = apps.get_model("escuela", "Curso")

    for curso in Curso.objects.filter(turno__isnull=True):
        turno = None
        if curso.nivel == "JARDIN":
            turno = time(12, 25)
        elif curso.nivel == "SECUNDARIA":
            turno = time(13, 30)
        elif curso.nivel == "PRIMARIA":
            m = re.search(r"\d+", curso.curso or "")
            if m:
                grado = int(m.group())
                if 1 <= grado <= 3:
                    turno = time(12, 30)
                elif 4 <= grado <= 7:
                    turno = time(13, 0)
        if turno:
            curso.turno = turno
            curso.save(update_fields=["turno"])


class Migration(migrations.Migration):

    dependencies = [
        ("escuela", "0004_curso_turno"),
    ]

    operations = [
        # Al revertir no se borran los turnos (se deja como está).
        migrations.RunPython(cargar_turnos, migrations.RunPython.noop),
    ]
