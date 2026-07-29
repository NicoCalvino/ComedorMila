from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DeleteView, DetailView, UpdateView, CreateView
from django.db import transaction
from django.db.models import Q
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from decimal import Decimal, InvalidOperation

from transacciones.models import Transaccion, SolicitudCarga, DetalleCarga
from transacciones.forms import *

from kiosco.models import Tarjeta
from escuela.models import Cliente

class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser
    
class StaffUserRequireMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

# Vistas de Transaccion
## Lista de Transacciones
class TransaccionListView(SuperUserRequiredMixin, ListView):
    model=Transaccion
    template_name = "transacciones/lista_transacciones.html"
    context_object_name= "transacciones"

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-fecha')
        filtro_tipo = self.request.GET.get('concepto', 'todo')
        if filtro_tipo == 'carga':
            queryset = queryset.filter(concepto="CARGA SALDO")
        elif filtro_tipo == 'compra':
            queryset = queryset.filter(concepto="COMPRA")

        return queryset
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

## Detalle de Transacción
class TransaccionDetailView(SuperUserRequiredMixin, DetailView):
    model = Transaccion
    template_name = "transacciones/ver_transaccion.html"
    context_object_name = "transaccion"
    slug_field ="id"
    slug_url_kwarg = "id"

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

## Creación de Transacción de Compra    
class TransaccionCompraCreateView(StaffUserRequireMixin, SuperUserRequiredMixin, CreateView):
    model = Transaccion
    template_name = "transacciones/cargar_transaccion.html"
    form_class = TransaccionCompraForm
    success_url = reverse_lazy('nueva_compra')

    extra_context = {
        'titulo_pagina': 'Registrar Nueva Compra',
        'subtitulo':'Nueva Compra',
        'texto_boton': 'Confirmar Compra',
        'tipo': 'Compra',
        'color_boton': 'btn-primary'
    }

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.concepto = "COMPRA"

        tarjeta = form.cleaned_data.get('tarjeta_objeto')
        monto = form.cleaned_data.get('monto')
        if tarjeta is None or monto is None:
            return self.form_invalid(form)

        # Recalculamos el saldo con la fila BLOQUEADA para evitar condiciones de
        # carrera (dos compras simultáneas pisándose el saldo). La validación del
        # form es la primera capa de UX; esta es la autoritativa.
        with transaction.atomic():
            tarjeta = Tarjeta.objects.select_for_update().get(pk=tarjeta.pk)

            if not tarjeta.habilitada:
                form.add_error('numero_tarjeta', "Esta tarjeta se encuentra deshabilitada.")
                return self.form_invalid(form)

            if tarjeta.cliente is None:
                form.add_error('numero_tarjeta', "La tarjeta no tiene un cliente asociado.")
                return self.form_invalid(form)

            limite = Decimal(tarjeta.cliente.limite)
            nuevo_saldo = tarjeta.saldo - Decimal(str(monto))
            if nuevo_saldo < -limite:
                form.add_error('numero_tarjeta', "Saldo insuficiente")
                return self.form_invalid(form)

            tarjeta.saldo = nuevo_saldo
            tarjeta.save()

            self.object.tarjeta = tarjeta
            self.object.save()

        messages.success(self.request, 'Compra registrada exitosamente',
            extra_tags='mensaje_local' )

        return HttpResponseRedirect(self.get_success_url())

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

## Creación de Transacción de Carga
class TransaccionCargaCreateView(SuperUserRequiredMixin, CreateView):
    model = Transaccion
    template_name = "transacciones/cargar_transaccion.html"
    form_class = TransaccionCargaForm

    extra_context = {
        'titulo_pagina': 'Registrar Nueva Carga de Saldo',
        'subtitulo':'Cargar Saldo',
        'texto_boton': 'Cargar Saldo',
        'tipo': 'Carga',
        'color_boton': 'btn-success'
    }

    def get_success_url(self):
        return reverse('lista_transacciones')

    def get_initial(self):
        initial = super().get_initial()
        
        tarjeta_codigo = self.request.GET.get('tarjeta_codigo')
        
        if tarjeta_codigo:
            initial['numero_tarjeta'] = tarjeta_codigo
            
        return initial

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.concepto = "CARGA SALDO"

        tarjeta = form.cleaned_data.get('tarjeta_objeto')
        monto = form.cleaned_data.get('monto')
        if tarjeta is None or monto is None:
            return self.form_invalid(form)

        # Fila bloqueada para no perder cargas concurrentes.
        with transaction.atomic():
            tarjeta = Tarjeta.objects.select_for_update().get(pk=tarjeta.pk)
            tarjeta.saldo = tarjeta.saldo + Decimal(str(monto))
            tarjeta.save()

            self.object.tarjeta = tarjeta
            self.object.save()

        return HttpResponseRedirect(self.get_success_url())

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

## Edición de Transacción
class TransaccionUpdateView(SuperUserRequiredMixin, UpdateView):
    model = Transaccion
    template_name = "transacciones/editar_transaccion.html"
    form_class = TransaccionUpdateForm
    success_url = reverse_lazy('lista_transacciones')
    slug_field ="id"
    slug_url_kwarg = "id"

    def form_valid(self, form):
        self.object = form.save(commit=False)
        monto_nuevo = form.cleaned_data.get('monto')
        if monto_nuevo is None:
            return self.form_invalid(form)

        with transaction.atomic():
            # Valores originales leídos de la DB (self.object ya tiene el monto nuevo).
            original = Transaccion.objects.get(pk=self.object.pk)
            monto_original = original.monto
            concepto_original = original.concepto

            # Fila de la tarjeta bloqueada para recalcular sobre saldo fresco.
            tarjeta = Tarjeta.objects.select_for_update().get(pk=original.tarjeta_id)

            if concepto_original == "COMPRA":
                nuevo_saldo = tarjeta.saldo + monto_original - Decimal(str(monto_nuevo))
                limite = Decimal(tarjeta.cliente.limite) if tarjeta.cliente else Decimal('2000')
                if nuevo_saldo < -limite:
                    form.add_error('monto', "Saldo insuficiente")
                    return self.form_invalid(form)
            else:
                nuevo_saldo = tarjeta.saldo - monto_original + Decimal(str(monto_nuevo))

            tarjeta.saldo = nuevo_saldo
            tarjeta.save()

            self.object.tarjeta = tarjeta
            self.object.save()

        return HttpResponseRedirect(self.get_success_url())

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

## Eliminar Transacción
class TransaccionDeleteView(SuperUserRequiredMixin, DeleteView):
    model = Transaccion
    template_name = "transacciones/confirmar_eliminar.html"
    success_url = reverse_lazy("lista_transacciones")

    def form_valid(self, form):
        transaccion = self.get_object()

        with transaction.atomic():
            # Tarjeta bloqueada: revertir el efecto de la transacción y eliminarla
            # de forma atómica para no dejar el saldo inconsistente.
            tarjeta = Tarjeta.objects.select_for_update().get(pk=transaccion.tarjeta_id)
            if transaccion.concepto == "CARGA SALDO":
                tarjeta.saldo = tarjeta.saldo - transaccion.monto
            else:
                tarjeta.saldo = tarjeta.saldo + transaccion.monto
            tarjeta.save()

            return super().form_valid(form)

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino
        
class BuscarClienteView(StaffUserRequireMixin, SuperUserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        numero_tarjeta = request.GET.get('numero_tarjeta', None)
        data = {
            'encontrado': False,
            'nombre': ""
        }
        
        if numero_tarjeta:
            # Filtramos por el código de 3 dígitos
            tarjeta = Tarjeta.objects.filter(codigo=numero_tarjeta).first()
            if tarjeta and tarjeta.cliente:
                data['encontrado'] = True
                data['nombre'] = f"{tarjeta.cliente.nombre} {tarjeta.cliente.apellido} | Saldo: $ {tarjeta.saldo:,.0f}".replace(",", ".")
        
        return JsonResponse(data)
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class BuscarClientePorNombreView(StaffUserRequireMixin, SuperUserRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        resultados = []
        
        if len(query) >= 3:
            # Buscamos coincidencias en nombre o apellido del Cliente
            clientes = Cliente.objects.filter(
                Q(nombre__icontains=query) | Q(apellido__icontains=query)
            ).distinct()[:10]
            
            for cliente in clientes:
                # Buscamos la tarjeta asociada a ese cliente
                tarjeta = Tarjeta.objects.filter(cliente=cliente).first()
                if tarjeta:
                    display_name = f"{cliente.nombre} {cliente.apellido} (Tarjeta: {tarjeta.codigo})"
                    resultados.append({
                        'nombre_completo': display_name,
                        'tarjeta_codigo': tarjeta.codigo
                    })
        
        return JsonResponse(resultados, safe=False)

    def handle_no_permission(self):
        return JsonResponse({'error': 'No autorizado'}, status=403)

# Vistas de Solicitud de Carga de Saldo
## Lista de Solicitudes        
class SolicitudDeCargaListView(LoginRequiredMixin, ListView):
    model=SolicitudCarga
    template_name = "transacciones/lista_solicitudes_de_carga.html"
    context_object_name= "solicitudes"

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-fecha')

        if not self.request.user.is_superuser:
            queryset = queryset.filter(usuario=self.request.user)
        filtro_tipo = self.request.GET.get('estado', 'todas')
        if filtro_tipo == 'aprobada':
            queryset = queryset.filter(estado="APROBADA")
        elif filtro_tipo == 'rechazada':
            queryset = queryset.filter(estado="RECHAZADA")
        elif filtro_tipo == 'pendiente':
            queryset = queryset.filter(estado="PENDIENTE")

        search_query = self.request.GET.get('usuario')
        
        if search_query and self.request.user.is_superuser:
            queryset = queryset.filter(
                Q(usuario__first_name__icontains=search_query) | Q(usuario__last_name__icontains=search_query)  
            )

        return queryset

## Creación de Solicitud
class SolicitudDeCargaCreateView(LoginRequiredMixin, CreateView):
    model = SolicitudCarga
    form_class = SolicitudCargaForm
    template_name = 'transacciones/solicitud_de_carga.html'
    success_url = reverse_lazy('lista_solicitudes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tarjetas'] = Tarjeta.objects.filter(
            cliente__usuario = self.request.user,
            habilitada = True
        ).select_related('cliente')
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.usuario = self.request.user
                self.object.monto = Decimal('0')
                self.object.save()

                tarjetas = Tarjeta.objects.filter(
                    cliente__usuario=self.request.user,
                    habilitada = True
                ).select_related('cliente')

                monto_total_cargado = Decimal('0')

                for tarjeta in tarjetas:
                    input_name = f"monto_{tarjeta.id}"
                    monto_raw = self.request.POST.get(input_name)
                    if not monto_raw:
                        continue
                    try:
                        monto = Decimal(monto_raw)
                    except InvalidOperation:
                        continue
                    if monto > 0:
                        DetalleCarga.objects.create(
                            solicitud=self.object,
                            tarjeta=tarjeta,
                            monto=monto
                        )
                        monto_total_cargado += monto

                if monto_total_cargado == 0:
                    raise ValueError("Debe ingresar un monto para al menos un alumno.")

                self.object.monto = monto_total_cargado
                self.object.save()

            messages.success(self.request, 'Solicitud enviada correctamente. Esperando aprobación.')
            return super().form_valid(form)
        
        except ValueError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, "Ocurrió un error inesperado al procesar la solicitud.")
            return self.form_invalid(form)

## Detalle de Solicitud
class SolicitudDeCargaDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model=SolicitudCarga
    template_name = "transacciones/detalle_solicitud_de_carga.html"
    context_object_name= "solicitud"
    slug_field ="code"
    slug_url_kwarg = "code"

    def test_func(self):
        solicitud = self.get_object()
        usuario_actual = self.request.user
        if usuario_actual.is_superuser:
            return True
        return solicitud.usuario == usuario_actual
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return redirect('lista_solicitudes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitud = self.object
        detalles_carga = DetalleCarga.objects.filter(solicitud=solicitud)
        context['detalles_carga'] = detalles_carga
        
        return context

## Edción de Solicitud
class SolicitudDeCargaUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = SolicitudCarga
    form_class = SolicitudCargaForm
    template_name = 'transacciones/editar_solicitud_de_carga.html'
    success_url = reverse_lazy('lista_solicitudes')
    slug_field = "code"
    slug_url_kwarg = "code"

    def test_func(self):
        solicitud = self.get_object()
        usuario_actual = self.request.user
        if usuario_actual.is_superuser:
            return True
        return solicitud.usuario == usuario_actual
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return redirect('lista_solicitudes')

    def get_queryset(self):
        solicitudes = SolicitudCarga.objects.filter(
            estado='PENDIENTE'
        )

        if not self.request.user.is_superuser:
            solicitudes = solicitudes.filter(usuario=self.request.user)

        return solicitudes


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        todas_tarjetas = Tarjeta.objects.filter(
            cliente__usuario=self.object.usuario,
            habilitada = True 
        ).select_related('cliente')

        detalles_existentes = self.object.detalles.all()
        mapa_montos = {d.tarjeta.id: float(d.monto) for d in detalles_existentes}
        
        for tarjeta in todas_tarjetas:
            tarjeta.monto_inicial = mapa_montos.get(tarjeta.id, 0)
        
        context['tarjetas_con_monto'] = todas_tarjetas
        
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.detalles.all().delete()

                tarjetas = Tarjeta.objects.filter(
                    cliente__usuario=self.request.user,
                    habilitada = True
                ).select_related('cliente')

                monto_total_cargado = Decimal('0')

                for tarjeta in tarjetas:
                    input_name = f"monto_{tarjeta.id}"
                    monto_raw = self.request.POST.get(input_name)
                    if not monto_raw:
                        continue
                    try:
                        monto = Decimal(monto_raw)
                    except InvalidOperation:
                        continue
                    if monto > 0:
                        DetalleCarga.objects.create(
                            solicitud=self.object,
                            tarjeta=tarjeta,
                            monto=monto
                        )
                        monto_total_cargado += monto

                if monto_total_cargado == 0:
                    raise ValueError("Debe ingresar un monto para al menos un alumno.")

                self.object.monto = monto_total_cargado
                self.object.save()
            return super().form_valid(form)
        
        except ValueError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, "Ocurrió un error inesperado al procesar la solicitud.")
            return self.form_invalid(form)

## Eliminación de Solicitud
class SolicitudDeCargaDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = SolicitudCarga
    template_name = "transacciones/confirmar_eliminar_carga_de_saldo.html"
    context_object_name= "solicitud"
    success_url = reverse_lazy("lista_solicitudes")

    def test_func(self):
        solicitud = self.get_object()
        usuario_actual = self.request.user
        if usuario_actual.is_superuser:
            return True
        return solicitud.usuario == usuario_actual

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return redirect('lista_solicitudes')

    def get_queryset(self):
        # Un usuario común solo puede borrar sus propias solicitudes y únicamente
        # mientras estén PENDIENTES (una aprobada/rechazada ya movió saldo).
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(usuario=self.request.user, estado='PENDIENTE')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitud = self.object
        detalles_carga = DetalleCarga.objects.filter(solicitud=solicitud)
        context['detalles_carga'] = detalles_carga
        
        return context

## Aprobación o Rechazo de Solicitud      
class GestionarSolicitudView(SuperUserRequiredMixin, View):
    def post(self, request, code):
        solicitud = get_object_or_404(SolicitudCarga, code=code)
        if solicitud.estado != 'PENDIENTE':
            messages.warning(request, "Esta solicitud ya fue procesada anteriormente.")
            return redirect('detalle_solicitud_de_carga', code=solicitud.code)
        
        accion = request.POST.get('accion')

        try:
            with transaction.atomic():
                if accion == 'aprobar':
                    solicitud.estado = 'APROBADA'
                    solicitud.save()

                    detalles = solicitud.detalles.all()

                    for detalle in detalles:
                        # Tarjeta bloqueada para acreditar sin perder cargas concurrentes.
                        tarjeta = Tarjeta.objects.select_for_update().get(pk=detalle.tarjeta_id)
                        Transaccion.objects.create(
                            tarjeta=tarjeta,
                            concepto="CARGA SALDO",
                            monto=detalle.monto,
                        )

                        tarjeta.saldo = tarjeta.saldo + detalle.monto
                        tarjeta.save()
                
                elif accion == 'rechazar':
                    
                    solicitud.estado = 'RECHAZADA'
                    solicitud.save()
                else:
                    messages.error(request, "Acción no válida.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error al procesar: {str(e)}")

        return redirect('lista_solicitudes')
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino