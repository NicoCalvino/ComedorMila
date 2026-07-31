"""Régimen de inasistencias avisadas.

Reglas acordadas:
- El padre avisa la falta SOLO el mismo día, hasta las 9:00 (hora local). Después
  de las 9 se considera sin aviso (no compensa).
- Solo vale para un día en que el alumno tiene comedor por su PLAN MENSUAL.
- Plan de 5 días: se acredita dinero = (precio_mensual_del_hijo / divisor) x
  porcentaje. divisor y porcentaje salen de ConfiguracionComedor (20 y 0.60).
- Plan de 1 a 4 días: se genera un ValeAFavor (almuerzo a favor flotante, no vence).
- Sin aviso: nada.
"""

from datetime import time
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from comedor.models import (
    Inasistencia, ValeAFavor, ValeDiario, ConfiguracionComedor,
    CuentaComedor, MovimientoComedor,
)
from comedor.cargos import _dias_semana_del_plan
from comedor.facturacion import facturacion_padre

LIMITE_AVISO = time(9, 0)


def _subtotal_mensual_hijo(cliente):
    """Precio mensual del hijo con su descuento familiar (0 si no hay plan/precio)."""
    fact = facturacion_padre(cliente.usuario)
    for hijo in fact['hijos']:
        if hijo['cliente'].pk == cliente.pk:
            return Decimal(hijo['subtotal'] or 0)
    return Decimal('0')


def puede_avisar(cliente, ahora=None):
    """(True, '') si se puede avisar la inasistencia ahora; si no (False, motivo)."""
    ahora = ahora or timezone.localtime()
    hoy = ahora.date()

    if ahora.time() >= LIMITE_AVISO:
        return False, "El aviso se puede hacer hasta las 9:00. Ya pasó el horario de hoy."

    vale = getattr(cliente, 'vale_mensual', None)
    if not vale:
        return False, "El alumno no tiene un plan mensual de comedor."

    if hoy.weekday() not in _dias_semana_del_plan(vale):
        return False, "Hoy el alumno no tiene comedor según su plan."

    if Inasistencia.objects.filter(cliente=cliente, fecha=hoy).exists():
        return False, "Ya avisaste la inasistencia de hoy para este alumno."

    return True, ""


def registrar_inasistencia(cliente, registrado_por=None, ahora=None):
    """Registra la inasistencia de hoy y aplica la compensación según el plan.

    Devuelve la Inasistencia creada. Lanza ValueError si no corresponde avisar.
    """
    ok, motivo = puede_avisar(cliente, ahora=ahora)
    if not ok:
        raise ValueError(motivo)

    ahora = ahora or timezone.localtime()
    hoy = ahora.date()
    vale = cliente.vale_mensual
    dias = len(_dias_semana_del_plan(vale))

    with transaction.atomic():
        inas = Inasistencia(cliente=cliente, fecha=hoy, avisado_en=timezone.now())

        if dias == 5:
            # Devolución de dinero (crédito en la cuenta).
            config = ConfiguracionComedor.get_solo()
            subtotal = _subtotal_mensual_hijo(cliente)
            valor_dia = subtotal / config.divisor_valor_dia if config.divisor_valor_dia else Decimal('0')
            credito = (valor_dia * config.porcentaje_devolucion_inasistencia).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            inas.resultado = Inasistencia.DEVOLUCION
            inas.monto_devuelto = credito
            inas.save()
            if credito > 0:
                cuenta = CuentaComedor.para(cliente.usuario)
                mov = cuenta.agregar_movimiento(
                    MovimientoComedor.CREDITO_INASISTENCIA, -credito,
                    concepto=f"Crédito por inasistencia {hoy:%d/%m/%Y} - {cliente.nombre} {cliente.apellido}",
                    registrado_por=registrado_por,
                )
                inas.movimiento = mov
                inas.save(update_fields=['movimiento'])
        else:
            # Plan de 1 a 4 días: almuerzo a favor.
            inas.resultado = Inasistencia.VALE_A_FAVOR
            inas.save()
            ValeAFavor.objects.create(cliente=cliente, inasistencia=inas)

    return inas


def usar_vale_a_favor(vale_a_favor, fecha, usuario=None):
    """Usa un almuerzo a favor eligiendo un día futuro: crea un ValeDiario gratis
    (sin cargo). Marca el vale a favor como usado. Lanza ValueError si no aplica."""
    if vale_a_favor.usado:
        raise ValueError("Este almuerzo a favor ya fue usado.")

    hoy = timezone.localdate()
    if fecha < hoy:
        raise ValueError("Elegí un día de hoy en adelante.")
    if fecha.weekday() >= 5:
        raise ValueError("El comedor no funciona los fines de semana.")

    cliente = vale_a_favor.cliente
    if ValeDiario.objects.filter(cliente=cliente, fecha=fecha, cancelado=False).exists():
        raise ValueError("El alumno ya tiene un vale cargado para ese día.")

    with transaction.atomic():
        vale = ValeDiario(
            cliente=cliente,
            usuario=usuario or cliente.usuario,
            fecha=fecha,
            comentarios="Almuerzo a favor (inasistencia)",
        )
        vale._skip_cargo = True  # gratis: la señal no cobra
        vale.save()

        vale_a_favor.usado = True
        vale_a_favor.fecha_uso = fecha
        vale_a_favor.vale_diario = vale
        vale_a_favor.save(update_fields=['usado', 'fecha_uso', 'vale_diario'])

    return vale
