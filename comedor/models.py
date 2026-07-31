from decimal import Decimal
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from users.models import Perfil
from kiosco.models import Cliente
from escuela.models import Colegio


def comprobante_pago_comedor_upload_to(instance, filename):
    return f"comprobantes_comedor/{instance.usuario.email}/{filename}"

def picture_upload_to(instance, filename):
    return f"comprobantes/{instance.usuario.email}/{filename}"

class Precio(models.Model):
    OPCIONES = (
        ("PRIMARIA/SECUNDARIA", "Primaria/Secundaria"),
        ("JARDIN", "Jardin"),
    )

    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE, null=False)
    alm_por_sem = models.IntegerField(null=False)
    nivel = models.CharField(choices=OPCIONES, null=False)
    nro_de_cliente = models.IntegerField(null=False)
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
    # Fecha desde la que rige esta configuración de plan. Se usa para prorratear
    # el cargo mensual cuando el alta/cambio cae a mitad de mes. Null = vigente
    # desde antes (se cobra el mes completo).
    vigente_desde = models.DateField(null=True, blank=True)

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


# ---------------------------------------------------------------------------
# CUENTA DE COMEDOR (circuito separado del kiosco)
# ---------------------------------------------------------------------------
# Saldo persistente de comedor por familia. NUNCA toca Tarjeta.saldo ni las
# transacciones del kiosco. El saldo es cache de la suma de movimientos.
# Convención de signo: saldo = suma de montos firmados de los movimientos.
#   - Cargos (mensual, vale diario)         -> monto POSITIVO  (aumentan deuda)
#   - Pagos, créditos por inasistencia      -> monto NEGATIVO  (bajan la deuda)
#   - Ajustes                               -> monto +/- según corresponda
# Positivo = el cliente DEBE; negativo = tiene saldo a favor.

class ConfiguracionComedor(models.Model):
    """Configuración global del comedor (singleton, pk=1)."""
    porcentaje_devolucion_inasistencia = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("0.60"),
        help_text="Fracción devuelta por inasistencia avisada en plan de 5 días (0.60 = 60%).",
    )
    divisor_valor_dia = models.PositiveIntegerField(
        default=20,
        help_text="Divisor del precio mensual para obtener el valor de un día (por defecto 20).",
    )
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de comedor"
        verbose_name_plural = "Configuración de comedor"

    def __str__(self):
        return "Configuración de comedor"

    def save(self, *args, **kwargs):
        self.pk = 1  # Singleton: siempre la misma fila.
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CuentaComedor(models.Model):
    usuario = models.OneToOneField(
        Perfil, on_delete=models.CASCADE, related_name='cuenta_comedor',
    )
    saldo = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Positivo = debe; negativo = a favor. Cache de la suma de movimientos.",
    )
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cuenta de comedor"
        verbose_name_plural = "Cuentas de comedor"

    def __str__(self):
        return f"Cuenta comedor de {self.usuario} (saldo {self.saldo})"

    @classmethod
    def para(cls, usuario):
        """Devuelve (o crea) la cuenta de comedor de un usuario/padre."""
        cuenta, _ = cls.objects.get_or_create(usuario=usuario)
        return cuenta

    def recalcular_saldo(self):
        """Recalcula el saldo desde los movimientos, con bloqueo de fila."""
        with transaction.atomic():
            cuenta = CuentaComedor.objects.select_for_update().get(pk=self.pk)
            total = cuenta.movimientos.aggregate(s=models.Sum('monto'))['s'] or Decimal("0.00")
            cuenta.saldo = total
            cuenta.save(update_fields=['saldo', 'actualizado'])
            self.saldo = total
        return self.saldo

    def agregar_movimiento(self, tipo, monto, concepto="", periodo=None,
                           registrado_por=None, fecha=None, vale_diario=None):
        """Crea un movimiento firmado y actualiza el saldo de forma atómica.

        `monto` debe venir ya firmado según la convención (cargos +, pagos/créditos -).
        """
        with transaction.atomic():
            mov = MovimientoComedor.objects.create(
                cuenta=self,
                tipo=tipo,
                monto=monto,
                concepto=concepto,
                periodo=periodo,
                registrado_por=registrado_por,
                fecha=fecha or timezone.now(),
                vale_diario=vale_diario,
            )
            self.recalcular_saldo()
        return mov


class MovimientoComedor(models.Model):
    CARGO_MENSUAL = 'CARGO_MENSUAL'
    CARGO_VALE_DIARIO = 'CARGO_VALE_DIARIO'
    PAGO = 'PAGO'
    AJUSTE = 'AJUSTE'
    CREDITO_INASISTENCIA = 'CREDITO_INASISTENCIA'
    TIPOS = (
        (CARGO_MENSUAL, "Cargo mensual"),
        (CARGO_VALE_DIARIO, "Cargo vale diario"),
        (PAGO, "Pago"),
        (AJUSTE, "Ajuste"),
        (CREDITO_INASISTENCIA, "Crédito por inasistencia"),
    )

    cuenta = models.ForeignKey(
        CuentaComedor, on_delete=models.CASCADE, related_name='movimientos',
    )
    tipo = models.CharField(max_length=30, choices=TIPOS)
    monto = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Firmado: positivo suma deuda (cargos); negativo la baja (pagos/créditos).",
    )
    concepto = models.CharField(max_length=200, blank=True, default="")
    periodo = models.CharField(
        max_length=7, null=True, blank=True,
        help_text="AAAA-MM (solo para cargos mensuales).",
    )
    fecha = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        Perfil, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # Vale diario que originó este movimiento (cargo o su reverso), si aplica.
    vale_diario = models.ForeignKey(
        'comedor.ValeDiario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movimientos_comedor',
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['cuenta', 'periodo'],
                condition=models.Q(tipo='CARGO_MENSUAL'),
                name='unico_cargo_mensual_por_periodo',
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.monto} ({self.cuenta.usuario})"


class SolicitudPagoComedor(models.Model):
    PENDIENTE = 'PENDIENTE'
    APROBADO = 'APROBADO'
    RECHAZADO = 'RECHAZADO'
    ESTADOS = (
        (PENDIENTE, "Pendiente"),
        (APROBADO, "Aprobado"),
        (RECHAZADO, "Rechazado"),
    )

    usuario = models.ForeignKey(
        Perfil, on_delete=models.CASCADE, related_name='pagos_comedor',
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    comprobante = models.ImageField(
        upload_to=comprobante_pago_comedor_upload_to, null=True, blank=True,
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDIENTE)
    creado = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)
    resuelto_por = models.ForeignKey(
        Perfil, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    movimiento = models.OneToOneField(
        MovimientoComedor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitud_pago',
    )

    class Meta:
        ordering = ['-creado']
        verbose_name = "Solicitud de pago de comedor"
        verbose_name_plural = "Solicitudes de pago de comedor"

    def __str__(self):
        return f"Pago comedor {self.monto} de {self.usuario} [{self.estado}]"

    def aprobar(self, admin=None):
        """Aprueba el pago: registra el movimiento PAGO (baja la deuda) y marca
        la solicitud como aprobada. Idempotente (solo actúa si está PENDIENTE)."""
        if self.estado != self.PENDIENTE:
            return None
        cuenta = CuentaComedor.para(self.usuario)
        mov = cuenta.agregar_movimiento(
            MovimientoComedor.PAGO, -self.monto,
            concepto="Pago de comedor", registrado_por=admin,
        )
        self.estado = self.APROBADO
        self.resuelto_en = timezone.now()
        self.resuelto_por = admin
        self.movimiento = mov
        self.save(update_fields=['estado', 'resuelto_en', 'resuelto_por', 'movimiento'])
        return mov

    def rechazar(self, admin=None):
        """Rechaza el pago (no toca el saldo). Idempotente."""
        if self.estado != self.PENDIENTE:
            return None
        self.estado = self.RECHAZADO
        self.resuelto_en = timezone.now()
        self.resuelto_por = admin
        self.save(update_fields=['estado', 'resuelto_en', 'resuelto_por'])
        return self


class Inasistencia(models.Model):
    DEVOLUCION = 'DEVOLUCION'
    VALE_A_FAVOR = 'VALE_A_FAVOR'
    SIN_COMPENSACION = 'SIN_COMPENSACION'
    RESULTADOS = (
        (DEVOLUCION, "Devolución de dinero (plan 5 días)"),
        (VALE_A_FAVOR, "Vale a favor (plan 1-4 días)"),
        (SIN_COMPENSACION, "Sin compensación (aviso tardío)"),
    )

    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name='inasistencias',
    )
    fecha = models.DateField(help_text="Día de la ausencia.")
    avisado_en = models.DateTimeField(default=timezone.now)
    resultado = models.CharField(max_length=20, choices=RESULTADOS)
    monto_devuelto = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    movimiento = models.ForeignKey(
        MovimientoComedor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )

    class Meta:
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'fecha'], name='una_inasistencia_por_cliente_dia',
            ),
        ]

    def __str__(self):
        return f"Inasistencia {self.cliente} {self.fecha} ({self.get_resultado_display()})"


class ValeAFavor(models.Model):
    """Almuerzo a favor (crédito flotante) generado por una inasistencia de un
    alumno con plan de 1 a 4 días. No vence; se usa eligiendo un día futuro."""
    cliente = models.ForeignKey(
        Cliente, on_delete=models.CASCADE, related_name='vales_a_favor',
    )
    inasistencia = models.OneToOneField(
        Inasistencia, on_delete=models.CASCADE, related_name='vale_a_favor',
        null=True, blank=True,
    )
    creado = models.DateTimeField(auto_now_add=True)
    usado = models.BooleanField(default=False)
    fecha_uso = models.DateField(
        null=True, blank=True,
        help_text="Día futuro elegido para usar el almuerzo a favor.",
    )
    vale_diario = models.OneToOneField(
        'comedor.ValeDiario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='origen_a_favor',
        help_text="ValeDiario gratis generado al usar este vale a favor.",
    )

    class Meta:
        ordering = ['-creado']
        verbose_name = "Vale a favor"
        verbose_name_plural = "Vales a favor"

    def __str__(self):
        estado = "usado" if self.usado else "disponible"
        return f"Vale a favor de {self.cliente} ({estado})"


@receiver(post_save, sender=ValeDiario)
def _vale_diario_actualiza_cuenta(sender, instance, created, **kwargs):
    """Al crear un vale diario se cobra a la cuenta de comedor; al cancelar un
    día que todavía no pasó se acredita. Se saltea si el vale es 'a favor'
    (gratis, atributo _skip_cargo puesto por la redención de un ValeAFavor)."""
    if getattr(instance, '_skip_cargo', False):
        return
    # Import diferido para evitar import circular (cargos importa comedor.models).
    from comedor.cargos import registrar_cargo_vale_diario, revertir_cargo_vale_diario
    if created and not instance.cancelado:
        registrar_cargo_vale_diario(instance)
    elif instance.cancelado:
        revertir_cargo_vale_diario(instance)

