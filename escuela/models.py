from django.db import models
from django.apps import apps
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date

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