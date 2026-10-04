"""Cálculos de la cuenta corriente mensual del colegio.

neto del mes = canon - consumos. Positivo: el kiosco le paga al colegio.
Negativo: los consumos superaron al canon y el colegio le debe al kiosco.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from escuela.models import MovimientoColegio, MesColegioPagado


def movimientos_del_mes(colegio, year, month):
    return MovimientoColegio.objects.filter(
        colegio=colegio, fecha__year=year, fecha__month=month,
    ).order_by("fecha", "id")


def mes_pagado(colegio, year, month):
    """El registro MesColegioPagado del mes, o None si no está pagado."""
    return MesColegioPagado.objects.filter(colegio=colegio, year=year, month=month).first()


def resumen_mes(colegio, year, month):
    movimientos = movimientos_del_mes(colegio, year, month)
    consumos = (movimientos.filter(tipo=MovimientoColegio.CONSUMO)
                .aggregate(total=Sum("monto"))["total"] or Decimal("0"))
    canon_mov = movimientos.filter(tipo=MovimientoColegio.CANON).first()
    canon = canon_mov.monto if canon_mov else None
    neto = canon - consumos if canon is not None else None
    return {
        "movimientos": movimientos,
        "consumos": consumos,
        "canon": canon,
        "neto": neto,
        "pagado": mes_pagado(colegio, year, month),
    }


def mes_anterior(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def mes_siguiente(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def nombre_mes(year, month):
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return f"{meses[month - 1]} {year}"
