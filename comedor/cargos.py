"""Generación de cargos mensuales de comedor.

Reglas:
- El cargo mensual se emite UNO POR HIJO (con el descuento familiar aplicado,
  ver comedor/facturacion.py). SIEMPRE se cobra el mes completo (no se
  prorratea). Si hace falta ajustar un cargo (una bonificación, una baja a
  mitad de mes), el admin edita el movimiento en el panel y el saldo se
  recalcula solo.
- Idempotente POR HIJO: volver a generar el mismo período le cobra únicamente a
  los hijos que todavía no tienen su cargo (un alta a mitad de mes), sin tocar
  ni duplicar los cargos ya emitidos.
- A los hijos que se agregan después, el descuento familiar les asigna la
  posición que sigue a la de los hijos ya facturados. Así el alta de un hermano
  nunca cambia (ni re-cobra) lo que ya se le facturó al resto.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from users.models import Perfil
from comedor.models import CuentaComedor, MovimientoComedor, Precio
from comedor.facturacion import facturacion_padre, planes_padre, precio_plan

# Orden lunes..viernes == weekday() 0..4
_DIAS_PLAN = ('lunes', 'martes', 'miercoles', 'jueves', 'viernes')


def _dias_semana_del_plan(vale):
    return {i for i, attr in enumerate(_DIAS_PLAN) if getattr(vale, attr)}


def _nombre(cliente):
    return f"{cliente.nombre} {cliente.apellido}".strip()


def cargo_mensual_padre(usuario, year, month):
    """Devuelve (total, detalle) del cargo mensual (mes completo) de una familia."""
    fact = facturacion_padre(usuario)
    total = Decimal('0.00')
    detalle = []
    for hijo in fact['hijos']:
        monto = Decimal(hijo['subtotal'] or 0)
        detalle.append({'cliente': hijo['cliente'], 'subtotal': monto, 'monto': monto})
        total += monto
    return total, detalle


def cargos_del_periodo(cuenta, periodo):
    """Movimientos CARGO_MENSUAL de una cuenta para un período."""
    return list(
        cuenta.movimientos
        .filter(tipo=MovimientoComedor.CARGO_MENSUAL, periodo=periodo)
        .select_related('cliente')
    )


def detalle_esperado(usuario):
    """Lo que le corresponde pagar hoy a cada hijo de una familia (mes completo).

    Lista de dicts {cliente, dias, vigente_desde, esperado} en el orden del
    descuento familiar (hijo 1, hijo 2, ...).
    """
    detalle = []
    for indice, vale in enumerate(planes_padre(usuario), start=1):
        detalle.append({
            'cliente': vale.cliente,
            'dias': vale.dias_semana,
            'vigente_desde': vale.vigente_desde,
            'esperado': Decimal(precio_plan(vale.cliente, vale.dias_semana, indice) or 0),
        })
    return detalle


def _subconjuntos(items):
    """Subconjuntos no vacíos de una lista chica (los hijos de una familia)."""
    resultado = [[]]
    for item in items:
        resultado += [sub + [item] for sub in resultado]
    return [sub for sub in resultado if sub]


def _hijos_cubiertos_por_cargos_viejos(cargos_viejos, hijos_sin_cargo):
    """Deduce por importe a qué hijos cubre un cargo viejo (sin detalle).

    Los cargos anteriores al detalle por hijo son un único movimiento por
    familia. Si hay UNA sola combinación de hijos cuyos importes suman
    exactamente lo cobrado, ésa es la lectura del cargo viejo y devolvemos ese
    conjunto de ids. Si hay varias combinaciones posibles (o ninguna),
    devolvemos None: no se adivina y la familia se regulariza a mano.
    """
    if len(hijos_sin_cargo) > 8:
        return None
    total_viejo = sum((c.monto for c in cargos_viejos), Decimal('0.00'))
    coincidencias = [
        sub for sub in _subconjuntos(hijos_sin_cargo)
        if sum((h['esperado'] for h in sub), Decimal('0.00')) == total_viejo
    ]
    if len(coincidencias) != 1:
        return None
    return {h['cliente'].id for h in coincidencias[0]}


def _hijos_ya_cobrados(cargos, detalle):
    """Ids de los hijos que ya tienen cubierto el período, o None si no se sabe.

    None = hay un cargo viejo sin detalle que no se pudo atribuir por importe.
    """
    ya = {c.cliente_id for c in cargos if c.cliente_id}
    viejos = [c for c in cargos if c.cliente_id is None]
    if not viejos:
        return ya
    cubiertos = _hijos_cubiertos_por_cargos_viejos(
        viejos, [d for d in detalle if d['cliente'].id not in ya],
    )
    if cubiertos is None:
        return None
    return ya | cubiertos


def generar_cargos_familia(usuario, periodo, registrado_por=None, cuenta=None):
    """Cobra el mes a los hijos de una familia que todavía no tienen cargo.

    Devuelve (creados, motivo): ``creados`` es la lista de movimientos nuevos y
    ``motivo`` explica por qué no se creó ninguno (None si se creó al menos
    uno). Nunca modifica ni duplica un cargo ya emitido.
    """
    cuenta = cuenta or CuentaComedor.para(usuario)
    detalle = detalle_esperado(usuario)
    ya_cobrados = _hijos_ya_cobrados(cargos_del_periodo(cuenta, periodo), detalle)

    if ya_cobrados is None:
        return [], 'cargo_sin_detalle'

    pendientes = [d for d in detalle if d['cliente'].id not in ya_cobrados]
    if not pendientes:
        return [], 'ya_generado'

    # Los hijos ya facturados ocupan los primeros lugares del descuento familiar:
    # al que se suma después se le cobra la posición que sigue. Así el alta de un
    # hermano nunca cambia (ni re-cobra) lo que ya se le facturó al resto.
    posicion = len(ya_cobrados)
    creados = []
    for hijo in pendientes:
        monto = Decimal(precio_plan(hijo['cliente'], hijo['dias'], posicion + 1) or 0)
        if monto <= 0:
            continue  # sin precio cargado para esa combinación: no ocupa lugar
        posicion += 1
        creados.append(cuenta.agregar_movimiento(
            MovimientoComedor.CARGO_MENSUAL, monto,
            concepto=f"Cargo mensual {periodo} - {_nombre(hijo['cliente'])}",
            periodo=periodo, cliente=hijo['cliente'], registrado_por=registrado_por,
        ))

    if not creados:
        return [], 'sin_monto'
    return creados, None


def generar_cargos_mensuales(year, month, registrado_por=None):
    """Genera el CARGO_MENSUAL de cada hijo con plan, para el período dado.

    Idempotente por hijo: omite a los que ya tienen el cargo de ese período, así
    que es seguro (y es la forma correcta) volver a correrlo cuando alguien se
    anota a mitad de mes. Devuelve un resumen con lo creado y lo omitido.
    """
    periodo = f"{year:04d}-{month:02d}"
    creados = []
    omitidos = []
    total_general = Decimal('0.00')

    padres = Perfil.objects.filter(valemensual__isnull=False).distinct()
    for usuario in padres:
        movimientos, motivo = generar_cargos_familia(
            usuario, periodo, registrado_por=registrado_por,
        )
        if motivo:
            omitidos.append({'usuario': usuario, 'motivo': motivo})
            continue

        for mov in movimientos:
            creados.append({
                'usuario': usuario, 'cliente': mov.cliente, 'monto': mov.monto,
            })
            total_general += mov.monto

    return {
        'periodo': periodo,
        'creados': creados,
        'omitidos': omitidos,
        'total': total_general,
    }


# ---------------------------------------------------------------------------
# Control de desvíos: lo cobrado del mes vs. lo que corresponde hoy
# ---------------------------------------------------------------------------

def desvio_familia(usuario, periodo, cuenta=None):
    """Compara lo cobrado a una familia en un período contra lo que corresponde.

    Devuelve {usuario, cobrado, esperado, diferencia, hijos, sin_detalle}.
    ``diferencia`` > 0 = falta cobrar; < 0 = se cobró de más.
    """
    cuenta = cuenta or CuentaComedor.para(usuario)
    cargos = cargos_del_periodo(cuenta, periodo)

    # Los ajustes del período (regularizaciones, bonificaciones) también cuentan
    # como cobrado: si no, una familia ya regularizada seguiría marcada.
    ajustes = cuenta.movimientos.filter(
        tipo=MovimientoComedor.AJUSTE, periodo=periodo,
    )
    cobrado = (sum((c.monto for c in cargos), Decimal('0.00'))
               + sum((a.monto for a in ajustes), Decimal('0.00')))

    detalle = detalle_esperado(usuario)
    ya_cobrados = _hijos_ya_cobrados(cargos, detalle)
    cargos_por_hijo = {c.cliente_id: c.monto for c in cargos if c.cliente_id}

    hijos = []
    esperado = Decimal('0.00')
    for hijo in detalle:
        esperado += hijo['esperado']
        cubierto = ya_cobrados is not None and hijo['cliente'].id in ya_cobrados
        hijos.append({
            **hijo,
            'tiene_cargo': cubierto,
            'cobrado': cargos_por_hijo.get(hijo['cliente'].id),
        })

    return {
        'usuario': usuario,
        'cuenta': cuenta,
        'periodo': periodo,
        'cobrado': cobrado,
        'esperado': esperado,
        'diferencia': esperado - cobrado,
        'hijos': hijos,
        'sin_detalle': ya_cobrados is None,
    }


def desvios_del_periodo(year, month):
    """Familias cuyo cargo del período no coincide con lo que corresponde hoy.

    Es el control que hace visible el caso típico: alguien se anotó (o cambió el
    plan) después de generar el mes.
    """
    periodo = f"{year:04d}-{month:02d}"
    usuarios = Perfil.objects.filter(valemensual__isnull=False).distinct()
    desvios = [d for d in (desvio_familia(u, periodo) for u in usuarios)
               if d['diferencia'] != 0]
    desvios.sort(key=lambda d: -abs(d['diferencia']))
    return {
        'periodo': periodo,
        'desvios': desvios,
        'total_diferencia': sum((d['diferencia'] for d in desvios), Decimal('0.00')),
    }


def regularizar_familia(usuario, year, month, registrado_por=None):
    """Deja el cargo del período de una familia igual a lo que corresponde hoy.

    Primero le cobra a los hijos que no tienen su cargo (queda como un cargo
    mensual más, con nombre y todo). Si aun así queda diferencia (un cargo viejo
    que no se pudo atribuir, o un cambio de plan a mitad de mes), la salda con un
    AJUSTE del período. Nunca modifica los movimientos ya emitidos.
    """
    periodo = f"{year:04d}-{month:02d}"
    cuenta = CuentaComedor.para(usuario)

    creados, _motivo = generar_cargos_familia(
        usuario, periodo, registrado_por=registrado_por, cuenta=cuenta,
    )

    d = desvio_familia(usuario, periodo, cuenta=cuenta)
    ajuste = None
    if d['diferencia'] != 0:
        faltantes = [h for h in d['hijos'] if not h['tiene_cargo']]
        if len(faltantes) == 1 and faltantes[0]['esperado'] == d['diferencia']:
            detalle_txt = f" - {_nombre(faltantes[0]['cliente'])}"
        else:
            detalle_txt = ""
        ajuste = cuenta.agregar_movimiento(
            MovimientoComedor.AJUSTE, d['diferencia'],
            concepto=f"Ajuste cargo mensual {periodo}{detalle_txt}",
            periodo=periodo, registrado_por=registrado_por,
        )

    return {'creados': creados, 'ajuste': ajuste, 'periodo': periodo,
            'diferencia': d['diferencia']}


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
        vale_diario=vale, cliente=cliente,
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
        vale_diario=vale, cliente=vale.cliente,
    )
