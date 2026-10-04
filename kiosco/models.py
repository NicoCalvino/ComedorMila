from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator
from escuela.models import Cliente

class Tarjeta(models.Model):
    codigo = models.CharField(max_length=20, unique=True, null=False, validators=[MinLengthValidator(3)])
    saldo = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(-2000)])
    habilitada = models.BooleanField(default=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=True)

    fecha_activacion = models.DateTimeField(auto_now_add=True)
    fecha_ultima_modificacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.codigo}"


class RecaudacionEfectivo(models.Model):
    """Total recaudado en efectivo en el kiosco, una carga por día (solo admin)."""
    # Tope de DecimalField(max_digits=10): un valor mayor rompe la lectura de la lista.
    MONTO_MAXIMO = Decimal("99999999.99")

    fecha = models.DateField(
        unique=True,
        error_messages={"unique": "Ya hay una recaudación cargada para esa fecha."},
    )
    monto = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(MONTO_MAXIMO)],
    )
    observaciones = models.CharField(max_length=200, blank=True, default="")
    cargado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Recaudación en efectivo"
        verbose_name_plural = "Recaudaciones en efectivo"

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} - $ {self.monto}"
