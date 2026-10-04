from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.db.models import Q
from django.db.models.functions import Right 
from django.core.paginator import Paginator
from django.contrib import messages
from kiosco.models import *
from kiosco.forms import *
from transacciones.models import *
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.urls import reverse

## Historial completo de transacciones de Cliente
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def home_kiosco(request):    
    return render(request, "kiosco/home.html")

@login_required
def historial_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    if cliente.usuario != request.user:
        messages.error(request, 'No tienes permiso para ver el historial de ese cliente.')
        return redirect('home')
    movimientos_list = Transaccion.objects.filter(tarjeta__cliente=cliente).order_by('-fecha')
    
    paginator = Paginator(movimientos_list, 20)
    page_number = request.GET.get('page')
    movimientos = paginator.get_page(page_number)
    
    return render(request, 'kiosco/historial_completo_cliente.html', {
        'cliente': cliente,
        'movimientos': movimientos, 
        'page_obj': movimientos,    
        'is_paginated': True
    })

# Vistas de Tarjetas
## Lista de Tarjetas
@user_passes_test(lambda u: u.is_superuser )
def lista_tarjetas(request):
    busqueda = request.GET.get("codigo") 
    tarjetas_query = Tarjeta.objects.all()

    filtro = request.GET.get('filtro')
    if filtro == 'con_cliente':
        tarjetas_query = tarjetas_query.exclude(cliente__isnull=True)
    elif filtro == 'sin_cliente':
        tarjetas_query = tarjetas_query.filter(cliente__isnull=True)
    
    if busqueda:
        tarjetas_query = tarjetas_query.filter(
            Q(codigo__icontains = busqueda) | 
            Q(cliente__nombre__icontains=busqueda) | 
            Q(cliente__apellido__icontains=busqueda)
        )
    return render(request, 'kiosco/tarjetas.html',{"tarjetas":tarjetas_query})

## Creacion de Tarjetas
# @user_passes_test(lambda u: u.is_superuser)
# def crear_tarjeta(request):
#     if request.method == "POST":
#         form = TarjetaForm(request.POST)
#         if form.is_valid():
#             form.save()
#             if 'confirmar_y_crear_otra' in request.POST:
#                 messages.success(request, '¡La tarjeta se ha creado exitosamente!', 
#                     extra_tags='mensaje_local')
#                 return redirect("crear_tarjeta")
#             return redirect("lista_tarjetas")
#     else:
#         form = TarjetaForm()

#     return render(request, 'kiosco/crear_tarjeta.html', {'form':form})

# @user_passes_test(lambda u: u.is_superuser)
# def crear_tarjetas_masivo(request):
#     if request.method == 'POST':
#         form = TarjetasMasivoForm(request.POST)
#         if form.is_valid():
#             desde = form.cleaned_data['numero_desde']
#             hasta = form.cleaned_data['numero_hasta']
            
#             tarjetas_creadas = 0
#             tarjetas_existentes = 0

#             # Bucle para crear las tarjetas
#             for numero in range(desde, hasta + 1):

#                 codigo_tarjeta = str(numero).zfill(3) 

#                 # get_or_create evita que se dupliquen si la tarjeta ya existe
#                 obj, created = Tarjeta.objects.get_or_create(codigo=codigo_tarjeta)
#                 if created:
#                     tarjetas_creadas += 1
#                 else:
#                     tarjetas_existentes += 1
            
#             # Mensaje de éxito
#             if tarjetas_creadas > 0:
#                 messages.success(request, f'Se generaron {tarjetas_creadas} tarjetas correctamente.', extra_tags='mensaje_local')
#             if tarjetas_existentes > 0:
#                 messages.warning(request, f'{tarjetas_existentes} tarjetas ya existían y fueron ignoradas.', extra_tags='mensaje_local')

#             return redirect('lista_tarjetas') # Redirige a tu lista de tarjetas
#     else:
#         form = TarjetasMasivoForm()
        
#     return render(request, 'kiosco/crear_tarjetas_masivo.html',{'form': form})


## Ver detalle de Tarjeta
@user_passes_test(lambda u: u.is_superuser)
def ver_tarjeta(request, pk):
    tarjeta = get_object_or_404(Tarjeta, pk=pk)
    return render(request, 'kiosco/ver_tarjeta.html', {'tarjeta':tarjeta})

# ## Eliminar Tarjeta
# @user_passes_test(lambda u: u.is_superuser)
# def eliminar_tarjeta(request, pk):
#     tarjeta = get_object_or_404(Tarjeta, pk=pk)
#     if request.method == "POST":
#         tarjeta.delete()
#         return redirect('lista_tarjetas')
#     return render(request, "kiosco/eliminar_tarjeta.html",{
#         "tarjeta":tarjeta
#     })

# ## Asociar Tarjeta a cliente
# @user_passes_test(lambda u: u.is_superuser)
# def asociar_tarjeta(request, pk):
#     tarjeta = get_object_or_404(Tarjeta, pk=pk)
#     busqueda_cliente = request.GET.get("nombre") 
#     clientes_query = Cliente.objects.all()
#     if busqueda_cliente:
#         clientes_query = Cliente.objects.filter(
#             Q(nombre__icontains = busqueda_cliente) | Q(apellido__icontains=busqueda_cliente),
#         )

#     return render(request, 'kiosco/asociar_cliente_lista.html', {
#         'tarjeta': tarjeta,
#         'clientes': clientes_query,
#         'query': busqueda_cliente
#     })

# ## Confirmar Asociación de tarjeta
# @user_passes_test(lambda u: u.is_superuser)
# def asociar_tarjeta_confirmar(request, pk, cliente_pk):
#     tarjeta = get_object_or_404(Tarjeta, pk=pk)
#     cliente = get_object_or_404(Cliente, pk=cliente_pk)

#     if request.method == 'POST':
#         tarjeta.cliente = cliente
#         tarjeta.save()

#         return redirect('ver_tarjeta', pk=tarjeta.pk)
    
#     return render(request, 'kiosco/asociar_cliente_confirmar.html', {
#         'tarjeta': tarjeta,
#         'cliente': cliente
#     })

## Habilitar o Deshabilitar Tarjeta desde para Superuser
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def cambiar_estado_tarjeta(request, pk):
    tarjeta = get_object_or_404(Tarjeta, pk=pk)
    tarjeta.habilitada = not tarjeta.habilitada
    tarjeta.save()

    return redirect('ver_tarjeta', tarjeta.pk)

## Habilitar o Deshabilitar Tarjeta desde el usuario común
@login_required
@require_POST
def cambiar_estado_tarjeta_alumno(request, pk):
    tarjeta = get_object_or_404(Tarjeta, pk=pk)
    # Una tarjeta sin cliente asociado no puede gestionarse desde acá
    if tarjeta.cliente is None or tarjeta.cliente.usuario != request.user:
        messages.error(request, 'No puedes modificar esa tarjeta')
        return redirect('home')
    tarjeta.habilitada = not tarjeta.habilitada
    tarjeta.save()

    return redirect('ver_cliente', pk=tarjeta.cliente.pk)


# Recaudación en efectivo (solo superusuario)
def _mes_desde_request(request):
    """Lee ?mes=AAAA-MM; si falta o es inválido, usa el mes actual."""
    hoy = date.today()
    try:
        anio, mes = (int(x) for x in (request.GET.get("mes") or "").split("-"))
        return date(anio, mes, 1)
    except (ValueError, TypeError):
        return date(hoy.year, hoy.month, 1)


def _render_recaudacion(request, form, editando=None, existente=None):
    inicio = _mes_desde_request(request)
    if editando is not None and "mes" not in request.GET:
        inicio = editando.fecha.replace(day=1)
    fin = date(inicio.year + (inicio.month == 12), inicio.month % 12 + 1, 1)
    anterior = date(inicio.year - (inicio.month == 1), (inicio.month - 2) % 12 + 1, 1)

    registros = RecaudacionEfectivo.objects.filter(fecha__gte=inicio, fecha__lt=fin).select_related("cargado_por")
    total_mes = registros.aggregate(t=Sum("monto"))["t"] or 0
    hoy = date.today()
    return render(request, "kiosco/recaudacion_efectivo.html", {
        "form": form,
        "editando": editando,
        "existente": existente,
        "registros": registros,
        "total_mes": total_mes,
        "mes_actual": inicio,
        "mes_param": inicio.strftime("%Y-%m"),
        "mes_anterior": anterior.strftime("%Y-%m"),
        "mes_siguiente": fin.strftime("%Y-%m") if fin <= date(hoy.year, hoy.month, 1) else None,
    })


@user_passes_test(lambda u: u.is_superuser)
def recaudacion_efectivo(request):
    if request.method == "POST":
        form = RecaudacionEfectivoForm(request.POST)
        if form.is_valid():
            registro = form.save(commit=False)
            registro.cargado_por = request.user
            registro.save()
            messages.success(request, f"Recaudación del {registro.fecha:%d/%m/%Y} guardada.")
            return redirect(f"{request.path}?mes={registro.fecha:%Y-%m}")
        # Si la fecha ya estaba cargada, ofrecemos ir directo a editarla.
        existente = RecaudacionEfectivo.objects.filter(fecha=form.data.get("fecha") or None).first() \
            if form.has_error("fecha", "unique") else None
        return _render_recaudacion(request, form, existente=existente)
    return _render_recaudacion(request, RecaudacionEfectivoForm())


@user_passes_test(lambda u: u.is_superuser)
def editar_recaudacion_efectivo(request, pk):
    registro = get_object_or_404(RecaudacionEfectivo, pk=pk)
    if request.method == "POST":
        form = RecaudacionEfectivoForm(request.POST, instance=registro)
        if form.is_valid():
            registro = form.save()
            messages.success(request, f"Recaudación del {registro.fecha:%d/%m/%Y} actualizada.")
            return redirect(f"{reverse('recaudacion_efectivo')}?mes={registro.fecha:%Y-%m}")
    else:
        form = RecaudacionEfectivoForm(instance=registro)
    return _render_recaudacion(request, form, editando=registro)


@user_passes_test(lambda u: u.is_superuser)
@require_POST
def eliminar_recaudacion_efectivo(request, pk):
    registro = get_object_or_404(RecaudacionEfectivo, pk=pk)
    mes = registro.fecha.strftime("%Y-%m")
    fecha = registro.fecha
    registro.delete()
    messages.success(request, f"Se eliminó la recaudación del {fecha:%d/%m/%Y}.")
    return redirect(f"{reverse('recaudacion_efectivo')}?mes={mes}")
