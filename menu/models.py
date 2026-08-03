from django.db import models
from django.core.exceptions import ValidationError # Importante para las validaciones

class Plato(models.Model):
    CATEGORIAS = (
        ("PLATO PRINCIPAL", "Plato Principal"),
        ("PLATO ALTERNATIVO", "Plato Alternativo"),
        ("POSTRE", "Postre")
    )

    INGREDIENTES = (
        ("POLLO","Pollo"),
        ("CERDO","Cerdo"),
        ("CARNE PICADA","Carne Picada")
    )

    DIA_ASIGNADO = (
        ("LUNES", "Lunes"),
        ("MARTES", "Martes"),
        ("MIERCOLES", "Miercoles"),
        ("JUEVES", "Jueves"),
        ("VIERNES", "Viernes"),
    )
    
    nombre = models.CharField(max_length=200, null=False)
    dia_fijo = models.CharField(choices=DIA_ASIGNADO, max_length=10, null=True, blank=True)
    categoria = models.CharField(choices=CATEGORIAS, max_length=80, null=False)
    ingrediente_principal = models.CharField(choices=INGREDIENTES, max_length=80, null=True, blank=True)

    def __str__(self):
        return f"{self.nombre}"


class Menu(models.Model):
    DIAS = (
        ("LUNES", "Lunes"),
        ("MARTES", "Martes"),
        ("MIERCOLES", "Miercoles"),
        ("JUEVES", "Jueves"),
        ("VIERNES", "Viernes"),
    )

    fecha = models.DateField(null=False, unique=True)
    dia = models.CharField(choices=DIAS, max_length=9, blank=True)
    plato_principal = models.ForeignKey(
        Plato, 
        on_delete=models.CASCADE, 
        limit_choices_to={'categoria': 'PLATO PRINCIPAL'},
        related_name='menus_principales'
    )
    
    plato_alternativo = models.ForeignKey(
        Plato, 
        on_delete=models.CASCADE, 
        null=True,
        blank=True, 
        limit_choices_to={'categoria': 'PLATO ALTERNATIVO'},
        related_name='menus_alternativos'
    )
    
    postre = models.ForeignKey(
        Plato, 
        on_delete=models.CASCADE, 
        limit_choices_to={'categoria': 'POSTRE'},
        related_name='menus_postres'
    )

    def clean(self):
        """
        El método clean se encarga de las validaciones antes de guardar.
        """
        if self.fecha:
            # .weekday() devuelve: 0=Lunes, 1=Martes... 5=Sábado, 6=Domingo
            numero_dia = self.fecha.weekday()
            
            if numero_dia >= 5: # 5 o 6 son fin de semana
                raise ValidationError(
                    {'fecha': "No se pueden crear menús para días Sábado o Domingo."}
                )

    def save(self, *args, **kwargs):
        # Primero ejecutamos la validación manualmente (el admin lo hace solo, 
        # pero si guardas por código es mejor llamar a full_clean)
        self.full_clean()
        
        # Mapeo para asignar el nombre del día automáticamente
        traduccion_dias = {
            0: "LUNES",
            1: "MARTES",
            2: "MIERCOLES",
            3: "JUEVES",
            4: "VIERNES",
        }
        
        self.dia = traduccion_dias.get(self.fecha.weekday())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.dia} {self.fecha} - {self.plato_principal} {self.postre}"
    
class Feriado(models.Model):
    fecha = models.DateField(null=False)
    nombre = models.CharField(max_length=300, null=False)

    def __str__(self):
        return f"{self.fecha} {self.nombre}"


class MenuJardin(models.Model):
    """Menú fijo semanal para el nivel JARDIN.

    A diferencia del Menu de primaria/secundaria (que se arma por fecha),
    el menú de jardín es fijo: una sola fila por día de la semana
    (Lunes a Viernes) que se repite todas las semanas. Los platos se cargan
    como texto libre (no dependen del catálogo de Platos).
    """
    DIAS = (
        ("LUNES", "Lunes"),
        ("MARTES", "Martes"),
        ("MIERCOLES", "Miercoles"),
        ("JUEVES", "Jueves"),
        ("VIERNES", "Viernes"),
    )
    # Orden de los días para poder ordenarlos de Lunes a Viernes.
    ORDEN_DIAS = {"LUNES": 0, "MARTES": 1, "MIERCOLES": 2, "JUEVES": 3, "VIERNES": 4}

    dia = models.CharField(choices=DIAS, max_length=9, unique=True)
    plato_principal = models.CharField(max_length=200, blank=True, default="")
    postre = models.CharField(max_length=200, blank=True, default="")
    orden = models.PositiveSmallIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["orden"]
        verbose_name = "Menú de jardín"
        verbose_name_plural = "Menú de jardín"

    def save(self, *args, **kwargs):
        self.orden = self.ORDEN_DIAS.get(self.dia, 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Menú Jardín - {self.get_dia_display()}"
