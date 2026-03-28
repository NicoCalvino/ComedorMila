from django.db import models
from kiosco.models import Tarjeta
from users.models import Perfil
import uuid

def generate_code():
    return uuid.uuid4().hex

def picture_upload_to(instance, filename):
    return f"comprobantes/{instance.usuario.email}/{filename}"

class Transaccion(models.Model):
    CONCEPTOS = (
        ("CARGA","Carga"),
        ("COMPRA","Compra"),
    )
    fecha = models.DateTimeField(auto_now_add=True)
    tarjeta = models.ForeignKey(Tarjeta, on_delete=models.CASCADE, null=False)
    concepto = models.CharField(choices=CONCEPTOS, max_length=30, null=False)
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.concepto} de $ {self.monto}"
    
class SolicitudCarga(models.Model):
    ESTADOS = (
        ("APROBADA","Aprobada"),
        ("RECHAZADA","Rechazada"),
        ("PENDIENTE","Pendiente")
    )
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_ultima_modificacion = models.DateTimeField(auto_now=True)
    usuario = models.ForeignKey(Perfil, on_delete=models.CASCADE, null=False)
    monto = models.DecimalField(max_digits=10, decimal_places=2) 
    code = models.CharField(max_length=32,
                            unique=True,
                            default = generate_code
                            )
    comprobante = models.ImageField(
        upload_to=picture_upload_to,
        verbose_name="Comprobante",
        default= "default/noticket.png",
        null=True,
        blank=True
    )
    estado = models.CharField(choices=ESTADOS, default="PENDIENTE")

    def __str__(self):
        return f"{self.usuario} por $ {self.monto}"
    
class DetalleCarga(models.Model):
    solicitud = models.ForeignKey(SolicitudCarga, on_delete=models.CASCADE, related_name='detalles')
    tarjeta = models.ForeignKey(Tarjeta, on_delete=models.CASCADE)
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.tarjeta.codigo}: ${self.monto}"