"""Generación de cargos mensuales de comedor (con prorrateo por días de comedor).

Reglas acordadas:
- El cargo mensual de una familia = suma del costo de cada hijo (facturación con
  descuento familiar, ver comedor/facturacion.py), prorrateado por hijo.
- Prorrateo: si el plan del hijo tiene `vigente_desde` dentro del mes, se cobra
  solo la fracción de DÍAS DE COMEDOR del plan desde esa fecha hasta fin de mes.
  Se IGNORAN los feriados (v1). Si `vigente_desde` es null o anterior al mes, se
  cobra el mes completo (factor 1).
- Idempotente: no se cobra dos veces el mismo período (UniqueConstraint +
  chequeo previo).
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from users.models import Perfil
from comedor.models import CuentaComedor, MovimientoComedor, Precio
from comedor.facturacion import facturacion_padre

# Orden lunes..viernes == weekday() 0..4
_DIAS_PLAN = ('lunes', 'martes', 'miercoles', 'jueves', 'viernes')


def _dias_semana_del_plan(vale):
    return {i for i, attr in enumerate(_DIAS_PLAN) if getattr(vale, attr)}


def dias_comedor_en_mes(vale, year, month, desde=None):
    """Cantidad de fechas del mes cuyo día de semana está en el plan.

    Si `desde` se pasa, cuenta solo las fechas >= desde. Ignora feriados (v1).
    """
    dias = _dias_semana_del_plan(vale)
    if not dias:
        return 0
    total = 0
    for d in range(1, monthrange(year, month)[1] + 1):
        f = date(year, month, d)
        if f.weekday() in dias and (desde is None or f >= desde):
            total += 1
    return total


def factor_prorrateo(vale, year, month):
    """Fracción del mes a cobrar (Decimal 0..1) según `vigente_desde`."""
    vd = vale.vigente_desde
    primer_dia = date(year, month, 1)
    if not vd or vd <= primer_dia:
        return Decimal('1')
    ultimo_dia = date(year, month, monthrange(year, month)[1])
    if vd > ultimo_dia:
        return Decimal('0')  # el plan empieza después de este mes
    total = dias_comedor_en_mes(vale, year, month)
    if total == 0:
        return Decimal('1')  # sin días de comedor: no prorratear (evita 0/0)
    desde = dias_comedor_en_mes(vale, year, month, desde=vd)
    return Decimal(desde) / Decimal(total)


def cargo_mensual_padre(usuario, year, month):
    """Devuelve (total, detalle) del cargo mensual prorrateado de una familia."""
    fact = facturacion_padre(usuario)
    total = Decimal('0.00')
    detalle = []
    for hijo in fact['hijos']:
        cliente = hijo['cliente']
        subtotal = Decimal(hijo['subtotal'] or 0)
        vale = getattr(cliente, 'vale_mensual', None)
        factor = factor_prorrateo(vale, year, month) if vale else Decimal('1')
        monto = (subtotal * factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        detalle.append({
            'cliente': cliente, 'subtotal': subtotal, 'factor': factor, 'monto': monto,
        })
        total += monto
    return total, detalle


def generar_cargos_mensuales(year, month, registrado_por=None):
    """Genera el CARGO_MENSUAL de cada familia con plan, para el período dado.

    Idempotente: omite las familias que ya tienen el cargo de ese período.
    Devuelve un resumen con lo creado y lo omitido.
    """
    periodo = f"{year:04d}-{month:02d}"
    creados = []
    omitidos = []
    total_general = Decimal('0.00')

    padres = Perfil.objects.filter(valemensual__isnull=False).distinct()
    for usuario in padres:
        cuenta = CuentaComedor.para(usuario)
        ya_existe = cuenta.movimientos.filter(
            tipo=MovimientoComedor.CARGO_MENSUAL, periodo=periodo,
        ).exists()
        if ya_existe:
            omitidos.append({'usuario': usuario, 'motivo': 'ya_generado'})
            continue

        total, _detalle = cargo_mensual_padre(usuario, year, month)
        if total <= 0:
            omitidos.append({'usuario': usuario, 'motivo': 'sin_monto'})
            continue

        cuenta.agregar_movimiento(
            MovimientoComedor.CARGO_MENSUAL, total,
            concepto=f"Cargo mensual {periodo}",
            periodo=periodo, registrado_por=registrado_por,
        )
        creados.append({'usuario': usuario, 'monto': total})
        total_general += total

    return {
        'periodo': periodo,
        'creados': creados,
        'omitidos': omitidos,
        'total': total_general,
    }


# ---------------------------------------------------------------------------
# Cargos por vale diario (un almuerzo suelto)
# ---------------------------------------------------------------------------

def precio_vale_diario(cliente):
    """Precio de un almuerzo suelto = Precio(1 día/semana) / 4, según nivel y
    colegio del alumno. Sin descuento familiar. 0 si no hay precio cargado."""
    nivel = cliente.curso.nivel
    nivel_precio = "JARDIN" if nivel == "JARDIN" else "PRIMARIA/SECUNDARIA"
    p = Precio.objects.filter(
        alm_por_sem=1, nivel=nivel_precio, colegio=cliente.curso.colegio,
    ).first()
    if not p:
        return Decimal('0.00')
    return (Decimal(p.precio) / 4).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def registrar_cargo_vale_diario(vale):
    """Crea el CARGO_VALE_DIARIO en la cuenta de la familia (idempotente)."""
    if getattr(vale, '_skip_cargo', False) or vale.cancelado:
        return None
    if MovimientoComedor.objects.filter(
        vale_diario=vale, tipo=MovimientoComedor.CARGO_VALE_DIARIO,
    ).exists():
        return None
    cliente = vale.cliente
    monto = precio_vale_diario(cliente)
    if monto <= 0:
        return None
    cuenta = CuentaComedor.para(cliente.usuario)
    return cuenta.agregar_movimiento(
        MovimientoComedor.CARGO_VALE_DIARIO, monto,
        concepto=f"Vale diario {vale.fecha:%d/%m/%Y} - {cliente.nombre} {cliente.apellido}",
        vale_diario=vale,
    )


def revertir_cargo_vale_diario(vale):
    """Acredita el cargo de un vale diario cancelado, solo si el día no pasó."""
    if vale.fecha < timezone.localdate():
        return None  # el día ya pasó: no se devuelve
    cargo = MovimientoComedor.objects.filter(
        vale_diario=vale, tipo=MovimientoComedor.CARGO_VALE_DIARIO,
    ).first()
    if not cargo:
        return None
    ya_revertido = MovimientoComedor.objects.filter(
        vale_diario=vale, tipo=MovimientoComedor.AJUSTE, monto__lt=0,
    ).exists()
    if ya_revertido:
        return None
    return cargo.cuenta.agregar_movimiento(
        MovimientoComedor.AJUSTE, -cargo.monto,
        concepto=f"Crédito por cancelación de vale diario {vale.fecha:%d/%m/%Y}",
        vale_diario=vale,
    )
