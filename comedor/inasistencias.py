"""Régimen de inasistencias avisadas.

El padre puede avisar VARIAS ausencias de una sola vez, incluso de días futuros
(sin límite hacia adelante). Reglas:
- Solo se pueden avisar días de comedor del PLAN MENSUAL del alumno (no fines de
  semana ni días sin comedor), de hoy en adelante.
- Día de HOY: si ya pasaron las 9:00, se registra igual como inasistencia pero
  SIN compensación (deja constancia de que el chico no va). Antes de las 9 sí
  compensa.
- Días FUTUROS: siempre compensan (se avisan con anticipación).
- Compensación según el plan: 5 días -> crédito de dinero = (precio_mensual /
  divisor) x porcentaje; 1 a 4 días -> un almuerzo a favor (ValeAFavor).
- Constantes (porcentaje y divisor) de ConfiguracionComedor.
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
_NOMBRES_DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']


def _subtotal_mensual_hijo(cliente):
    """Precio mensual del hijo con su descuento familiar (0 si no hay plan/precio)."""
    fact = facturacion_padre(cliente.usuario)
    for hijo in fact['hijos']:
        if hijo['cliente'].pk == cliente.pk:
            return Decimal(hijo['subtotal'] or 0)
    return Decimal('0')


def tiene_plan(cliente):
    return getattr(cliente, 'vale_mensual', None) is not None


def dias_plan_legibles(cliente):
    """Nombres de los días de comedor del plan (para mostrar al padre)."""
    vale = getattr(cliente, 'vale_mensual', None)
    if not vale:
        return []
    return [_NOMBRES_DIAS[i] for i in sorted(_dias_semana_del_plan(vale))]


def _validar_dia(cliente, fecha, hoy):
    """Devuelve el motivo de rechazo (str) o None si el día es válido para avisar."""
    if fecha < hoy:
        return "es un día que ya pasó"
    vale = getattr(cliente, 'vale_mensual', None)
    if not vale:
        return "el alumno no tiene plan mensual"
    if fecha.weekday() not in _dias_semana_del_plan(vale):
        return "no es un día de comedor del plan"
    if Inasistencia.objects.filter(cliente=cliente, fecha=fecha).exists():
        return "ya estaba avisado"
    return None


def _compensar(cliente, inas):
    """Aplica la compensación (crédito o vale a favor) a una inasistencia ya creada."""
    dias = len(_dias_semana_del_plan(cliente.vale_mensual))
    if dias == 5:
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
                concepto=f"Crédito por inasistencia {inas.fecha:%d/%m/%Y} - {cliente.nombre} {cliente.apellido}",
            )
            inas.movimiento = mov
            inas.save(update_fields=['movimiento'])
    else:
        inas.resultado = Inasistencia.VALE_A_FAVOR
        inas.save()
        ValeAFavor.objects.create(cliente=cliente, inasistencia=inas)


def registrar_inasistencia_dia(cliente, fecha, ahora=None):
    """Registra la inasistencia de un día (hoy o futuro).

    Devuelve un dict {'fecha', 'resultado', 'monto'}. Lanza ValueError si el día
    no es válido (pasado, sin plan, no es día de comedor, o ya avisado).
    """
    ahora = ahora or timezone.localtime()
    hoy = ahora.date()

    motivo = _validar_dia(cliente, fecha, hoy)
    if motivo:
        raise ValueError(motivo)

    tardio = (fecha == hoy and ahora.time() >= LIMITE_AVISO)

    with transaction.atomic():
        inas = Inasistencia(cliente=cliente, fecha=fecha, avisado_en=timezone.now())
        if tardio:
            inas.resultado = Inasistencia.SIN_COMPENSACION
            inas.save()
        else:
            _compensar(cliente, inas)

    return {'fecha': fecha, 'resultado': inas.resultado, 'monto': inas.monto_devuelto}


def registrar_inasistencias(cliente, fechas, ahora=None):
    """Procesa una tanda de días. Devuelve {'ok': [dict...], 'errores': [(fecha, motivo)...]}."""
    ok, errores = [], []
    for fecha in fechas:
        try:
            ok.append(registrar_inasistencia_dia(cliente, fecha, ahora=ahora))
        except ValueError as e:
            errores.append((fecha, str(e)))
    return {'ok': ok, 'errores': errores}


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
