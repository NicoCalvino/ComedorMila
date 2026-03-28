from django.db import models
from users.models import Perfil
from kiosco.models import Cliente
from escuela.models import Colegio

def picture_upload_to(instance, filename):
    return f"comprobantes/{instance.usuario.email}/{filename}"

class Precio(models.Model):
    OPCIONES = (
        ("PRIMARIA/SECUNDARIA", "Primaria/Secundaria"),
        ("JARDIN", "Jardin"),
    )

    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, null=False)
    alm_por_sem = models.IntegerField(max_length=1, null=False)
    nivel = models.CharField(choices=OPCIONES, null=False)
    nro_de_cliente = models.IntegerField(max_length=1, null=False)
    precio = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f"{self.nivel} - {self.alm_por_sem} por semana - $ {self.precio}"

class ValeMensual(models.Model):
    usuario = models.ForeignKey(Perfil, on_delete=models.CASCADE, null=False)
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name='vale_mensual')
    lunes = models.BooleanField(default=False)
    martes = models.BooleanField(default=False)
    miercoles = models.BooleanField(default=False)
    jueves = models.BooleanField(default=False)
    viernes = models.BooleanField(default=False)
    comentarios = models.CharField(max_length=50, null=True, blank=True, default="")

    def __str__(self):
        return f"Vale Mensual de {self.usuario}"
    
class ValeDiario(models.Model):
    usuario = models.ForeignKey(Perfil, on_delete=models.CASCADE, null=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=False)
    fecha = models.DateField(null=False)
    cancelado = models.BooleanField(default=False)
    comentarios = models.CharField(max_length=50, null=True, blank=True, default="")
    comprobante = models.ImageField(
        upload_to=picture_upload_to,
        verbose_name="Picture",
        default= "default/noticket.png",
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Vale Diario de {self.usuario} para el día {self.fecha}"
    
class Asistencia(models.Model):
    fecha = models.DateField(null=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=False)
    turno = models.CharField(max_length=30)
    asistio= models.BooleanField()

    class Meta:
        unique_together = ('fecha', 'cliente')

    def __str__(self):
        return f"Asistencia {self.cliente} para el día {self.fecha}"

