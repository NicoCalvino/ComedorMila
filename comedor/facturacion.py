"""Cálculo de la facturación mensual de comedor de un padre.

Replica la misma lógica de ``ReporteFacturacionView`` (comedor/views.py):
cuenta los días/semana marcados en el Plan Mensual de cada alumno, aplica el
descuento familiar (el hijo con más días es el "hijo 1", el siguiente el
"hijo 2", etc., con tope en el 3er hijo; jardín siempre cuenta como hijo 1) y
busca el monto en la tabla ``Precio`` para (días/semana, colegio, nivel, nro
de hijo).

Se centraliza acá para que la página del padre (Saldo Comedor) y el reporte
de facturación del admin usen exactamente el mismo cálculo.
"""

from comedor.models import ValeMensual, Precio


def facturacion_padre(usuario):
    """Devuelve {'hijos': [...], 'total': Decimal/int} para un padre.

    Cada item de 'hijos' es un dict con: cliente, dias, nro_orden, subtotal.
    Solo se incluyen alumnos con Plan Mensual de al menos 1 día.
    """
    vales = list(
        ValeMensual.objects
        .filter(usuario=usuario)
        .select_related('cliente', 'cliente__curso', 'cliente__curso__colegio')
    )

    # Días marcados por vale (suma de booleanos lunes..viernes).
    for vale in vales:
        vale.dias_semana = sum([
            vale.lunes, vale.martes, vale.miercoles, vale.jueves, vale.viernes
        ])

    # Ordenamos por días descendente: define el orden de "hijo 1, 2, 3..."
    # para el descuento familiar.
    vales.sort(key=lambda v: v.dias_semana, reverse=True)

    hijos = []
    total = 0
    indice = 0

    for vale in vales:
        if vale.dias_semana == 0:
            continue

        indice += 1
        nro_hijo_clave = indice if indice <= 3 else 3

        nivel = vale.cliente.curso.nivel
        if nivel == "JARDIN":
            nro_hijo_clave = 1

        if nivel in ("PRIMARIA", "SECUNDARIA"):
            nivel = "PRIMARIA/SECUNDARIA"

        precio_obj = Precio.objects.filter(
            alm_por_sem=vale.dias_semana,
            colegio=vale.cliente.curso.colegio,
            nivel=nivel,
            nro_de_cliente=nro_hijo_clave,
        ).first()

        precio_monto = precio_obj.precio if precio_obj else 0

        hijos.append({
            'cliente': vale.cliente,
            'dias': vale.dias_semana,
            'nro_orden': indice,
            'subtotal': precio_monto,
        })
        total += precio_monto

    return {'hijos': hijos, 'total': total}
