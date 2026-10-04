from django.db import models
from django.apps import apps
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.utils import timezone

class Colegio(models.Model):
    nombre = models.CharField(max_length=100, null=False, unique=True)

    def __str__(self):
        return f"{self.nombre}"

class Curso(models.Model):
    OPCIONES = (
        ("JARDIN", "Jardin"),
        ("PRIMARIA", "Primaria"),
        ("SECUNDARIA","Secundaria")
    )

    curso = models.CharField(max_length=20, null=False)
    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, related_name='cursos', null=False)
    nivel = models.CharField(choices=OPCIONES, null=False)
    # Hora en la que almuerza el curso. Opcional: los cursos existentes quedan sin turno.
    turno = models.TimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.curso} - {self.nivel} - {self.colegio}"

class Cliente(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clientes', null=False)
    nombre = models.CharField(max_length=50, null=False)
    apellido = models.CharField(max_length=50, null=False)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='cursos', null=False)
    limite = models.DecimalField(max_digits=10, decimal_places=2, default=2000)

    @property
    def saldo_total(self):
        total = sum(tarjeta.saldo for tarjeta in self.tarjeta_set.all())
        return total
    
    @property
    def vales_diarios_pendientes(self):
        return self.valediario_set.filter(fecha__gte=date.today(),
            cancelado=False).order_by('fecha')[:3]

    def ultimos_movimientos(self):
        movimientos = []
        
        for tarjeta in self.tarjeta_set.all():
            movimientos .extend(tarjeta.transaccion_set.all())
        
        movimientos.sort(key=lambda x: x.fecha, reverse=True)
        
        return movimientos[:10]

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.curso}"

@receiver(post_save, sender=Cliente)
def crear_tarjeta_automaticamente(sender, instance, created, **kwargs):
    if created:
        # Esto se ejecuta tanto en la View normal como en la importación de Excel
        Tarjeta = apps.get_model('kiosco', 'Tarjeta')
        Tarjeta.objects.create(
            cliente=instance,
            codigo=str(instance.id).zfill(3), # Ajusta según tu necesidad de código
            saldo=0,
            habilitada=True
        )

# --- Cuenta corriente del colegio -------------------------------------------
# Registra lo que consume el colegio en el kiosco/comedor y el canon que el
# kiosco le paga por la concesión. Se liquida por mes:
#     neto a pagar al colegio = canon del mes - consumos del mes
# No se arrastra saldo de un mes a otro.

class MovimientoColegio(models.Model):
    CONSUMO = "CONSUMO"
    CANON = "CANON"
    TIPOS = (
        (CONSUMO, "Consumo del colegio"),
        (CANON, "Canon de concesión"),
    )

    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, related_name="movimientos_cuenta")
    tipo = models.CharField(max_length=10, choices=TIPOS, default=CONSUMO)
    concepto = models.CharField(max_length=200)
    # Siempre positivo: el signo lo da el tipo. Tope de la base: 99.999.999,99.
    monto = models.DecimalField(max_digits=10, decimal_places=2,
                                validators=[MinValueValidator(Decimal("0.01"))])
    # El mes del movimiento sale de esta fecha.
    fecha = models.DateField(default=timezone.localdate)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="+")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name = "Movimiento de cuenta del colegio"
        verbose_name_plural = "Movimientos de cuenta del colegio"

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} {self.get_tipo_display()}: {self.concepto} $ {self.monto}"


class MesColegioPagado(models.Model):
    """Marca un mes como pagado. Mientras exista, los movimientos de ese mes
    no se pueden cargar, editar ni borrar (hay que desmarcarlo primero)."""
    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, related_name="meses_pagados")
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    # Neto pagado al momento de marcarlo (canon - consumos). Negativo si el
    # colegio terminó debiéndole al kiosco.
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_pago = models.DateField(default=timezone.localdate)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="+")
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["colegio", "year", "month"], name="mes_colegio_pagado_unico"),
        ]
        verbose_name = "Mes pagado al colegio"
        verbose_name_plural = "Meses pagados al colegio"

    def __str__(self):
        return f"{self.colegio} {self.month:02d}/{self.year} pagado $ {self.monto_pagado}"
