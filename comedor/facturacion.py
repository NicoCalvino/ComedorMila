"""Cálculo de la facturación mensual de comedor de un padre.

Replica la misma lógica de ``ReporteFacturacionView`` (comedor/views.py):
cuenta los días/semana marcados en el Plan Mensual de cada alumno, aplica el
descuento familiar (el hijo con más días es el "hijo 1", el siguiente el
"hijo 2", etc., con tope en el 3er hijo; jardín siempre cuenta como hijo 1) y
busca el monto en la tabla ``Precio`` para (días/semana, colegio, nivel, nro
de hijo).

Se centraliza acá para que la página del padre (Saldo Comedor), el reporte de
facturación del admin y la generación de cargos mensuales (comedor/cargos.py)
usen exactamente el mismo cálculo.
"""

from comedor.models import ValeMensual, Precio


def planes_padre(usuario):
    """Planes mensuales de una familia, con ``dias_semana`` calculado y
    ordenados de más a menos días (ese orden define hijo 1, hijo 2, ...).

    Solo devuelve los planes con al menos 1 día marcado.
    """
    vales = list(
        ValeMensual.objects
        .filter(usuario=usuario)
        .select_related('cliente', 'cliente__curso', 'cliente__curso__colegio')
    )

    for vale in vales:
        vale.dias_semana = sum([
            vale.lunes, vale.martes, vale.miercoles, vale.jueves, vale.viernes
        ])

    vales = [v for v in vales if v.dias_semana > 0]
    # Orden por días descendente: define el orden de "hijo 1, 2, 3..." para el
    # descuento familiar. Desempate por id para que el orden sea estable.
    vales.sort(key=lambda v: (-v.dias_semana, v.id))
    return vales


def precio_plan(cliente, dias_semana, nro_hijo):
    """Precio mensual de un plan de ``dias_semana`` días para ``cliente``,
    ocupando la posición ``nro_hijo`` del descuento familiar.

    El descuento tiene tope en el 3er hijo y jardín siempre paga como hijo 1.
    Devuelve 0 si no hay precio cargado para esa combinación.
    """
    if dias_semana <= 0:
        return 0

    nro_hijo_clave = nro_hijo if nro_hijo <= 3 else 3

    nivel = cliente.curso.nivel
    if nivel == "JARDIN":
        nro_hijo_clave = 1

    if nivel in ("PRIMARIA", "SECUNDARIA"):
        nivel = "PRIMARIA/SECUNDARIA"

    precio_obj = Precio.objects.filter(
        alm_por_sem=dias_semana,
        colegio=cliente.curso.colegio,
        nivel=nivel,
        nro_de_cliente=nro_hijo_clave,
    ).first()

    return precio_obj.precio if precio_obj else 0


def facturacion_padre(usuario):
    """Devuelve {'hijos': [...], 'total': Decimal/int} para un padre.

    Cada item de 'hijos' es un dict con: cliente, dias, nro_orden, subtotal.
    Solo se incluyen alumnos con Plan Mensual de al menos 1 día.
    """
    hijos = []
    total = 0

    for indice, vale in enumerate(planes_padre(usuario), start=1):
        precio_monto = precio_plan(vale.cliente, vale.dias_semana, indice)

        hijos.append({
            'cliente': vale.cliente,
            'dias': vale.dias_semana,
            'nro_orden': indice,
            'subtotal': precio_monto,
        })
        total += precio_monto

    return {'hijos': hijos, 'total': total}
