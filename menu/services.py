from datetime import timedelta, date
from django.db.models import Q
from .models import Menu, Plato, Feriado

def obtener_plato_rotativo(fecha_proyectada, categoria="PLATO PRINCIPAL"):
    """
    Selecciona el plato (Principal o Postre) que toca según la rotación fija 
    definida en el modelo Plato (campo dia_fijo).
    """
    dias_map = {0: "LUNES", 1: "MARTES", 2: "MIERCOLES", 3: "JUEVES", 4: "VIERNES"}
    nombre_dia = dias_map.get(fecha_proyectada.weekday())

    if not nombre_dia:
        return None

    # Obtenemos los platos marcados para ese día en la base de datos
    platos_posibles = list(Plato.objects.filter(
        dia_fijo=nombre_dia, 
        categoria=categoria
    ).order_by('id'))

    if not platos_posibles:
        return None

    # Contamos cuántos menús de este día de la semana ya existen 
    # (Esto asegura que los feriados trasladen la lógica)
    conteo_historico = Menu.objects.filter(dia=nombre_dia).count()

    indice = conteo_historico % len(platos_posibles)
    return platos_posibles[indice]

def obtener_plato_alternativo(d):
    platos_posibles = Plato.objects.filter(
        dia_fijo=d, 
        categoria="PLATO ALTERNATIVO"
    ).first()

    if not platos_posibles:
        return None

    return platos_posibles

def obtener_plato_lunes_martes(fecha_actual, ingredientes_prohibidos_semana):
    """
    Lógica especial para Lunes y Martes:
    1. Evita ingredientes ya usados en la semana (Mié/Jue/Vie).
    2. Evita repetir el mismo plato de las últimas 3 semanas para ese día.
    """
    dias_map = {0: "LUNES", 1: "MARTES"}
    nombre_dia = dias_map.get(fecha_actual.weekday())
    
    # 1. Identificar platos de los últimos 3 lunes (o martes) anteriores
    ultimos_platos_ids = Menu.objects.filter(
        dia=nombre_dia, 
        fecha__lt=fecha_actual
    ).order_by('-fecha')[:3].values_list('plato_principal_id', flat=True)

    # 2. Filtrar platos en la DB
    platos_candidatos = Plato.objects.filter(
        dia_fijo=nombre_dia,
        categoria="PLATO PRINCIPAL"
    ).exclude(
        ingrediente_principal__in=ingredientes_prohibidos_semana
    ).exclude(
        id__in=ultimos_platos_ids
    )

    # Si el filtro es demasiado estricto, relajamos la restricción de "últimas 3 semanas"
    if not platos_candidatos.exists():
        platos_candidatos = Plato.objects.filter(
            dia_fijo=nombre_dia, 
            categoria="PLATO PRINCIPAL"
        ).exclude(ingrediente_principal__in=ingredientes_prohibidos_semana)

    return platos_candidatos.first()


def generar_menu_escolar(fecha_inicio_lunes, cantidad_semanas):
    """
    Proceso principal que genera el calendario de comidas semana por semana.
    """
    for s in range(cantidad_semanas):
        lunes_de_esta_semana = fecha_inicio_lunes + timedelta(weeks=s)
        prohibidos_esta_semana = set()

        # --- FASE 1: Días Fijos (Miércoles, Jueves, Viernes) ---
        # Los generamos primero para saber qué ingredientes prohibir el Lunes/Martes
        for d in [2, 3, 4]: 
            fecha = lunes_de_esta_semana + timedelta(days=d)
            
            # Si es feriado, no hacemos nada (el conteo no sube)
            if Feriado.objects.filter(fecha=fecha).exists():
                continue
            
            principal = obtener_plato_rotativo(fecha, "PLATO PRINCIPAL")
            postre = obtener_plato_rotativo(fecha, "POSTRE")
            alternativo = None
            if d == 4 or d == 2:
                alternativo = obtener_plato_alternativo(["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES"][d])

            if principal:
                Menu.objects.create(
                    fecha=fecha,
                    dia=["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES"][d],
                    plato_principal=principal,
                    plato_alternativo = alternativo,
                    postre=postre
                )
                if principal.ingrediente_principal:
                    prohibidos_esta_semana.add(principal.ingrediente_principal)

        # --- FASE 2: Días Dinámicos (Lunes, Martes) ---
        for d in [0, 1]:
            fecha = lunes_de_esta_semana + timedelta(days=d)
            
            if Feriado.objects.filter(fecha=fecha).exists():
                continue

            principal = obtener_plato_lunes_martes(fecha, list(prohibidos_esta_semana))
            postre = obtener_plato_rotativo(fecha, "POSTRE")

            if principal:
                Menu.objects.create(
                    fecha=fecha,
                    dia=["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES"][d],
                    plato_principal=principal,
                    postre=postre
                )
                # Actualizamos prohibidos para que el Martes no repita con el Lunes
                if principal.ingrediente_principal:
                    prohibidos_esta_semana.add(principal.ingrediente_principal)