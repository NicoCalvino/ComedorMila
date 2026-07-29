from django.db import models
from django.core.validators import MinValueValidator, MinLengthValidator
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
