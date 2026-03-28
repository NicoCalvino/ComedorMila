from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DeleteView, DetailView, UpdateView, CreateView
from django.db import transaction
from django.db.models import Q
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from transacciones.models import Transaccion, SolicitudCarga, DetalleCarga
from transacciones.forms import *

from kiosco.models import Tarjeta

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

        if 'tarjeta_objeto' in form.cleaned_data:
            tarjeta = form.cleaned_data['tarjeta_objeto']
            
            nuevo_saldo = form.cleaned_data['nuevo_saldo_tarjeta']

            tarjeta.saldo = nuevo_saldo
            tarjeta.save()

            self.object.tarjeta = tarjeta
        
        self.object.save()

        messages.success(self.request, 'Compra registrada exitosamente', 
            extra_tags='mensaje_local' )

        return super().form_valid(form)
    
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

        if 'tarjeta_objeto' in form.cleaned_data:
            tarjeta = form.cleaned_data['tarjeta_objeto']
            nuevo_saldo = form.cleaned_data['nuevo_saldo_tarjeta']

            tarjeta.saldo = nuevo_saldo
            tarjeta.save()

            self.object.tarjeta = tarjeta
        
        self.object.save()

        return super().form_valid(form)
    
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

        if 'tarjeta_objeto' in form.cleaned_data:
            tarjeta = form.cleaned_data['tarjeta_objeto']
            nuevo_saldo = form.cleaned_data['nuevo_saldo_tarjeta']

            tarjeta.saldo = nuevo_saldo
            tarjeta.save()

            self.object.tarjeta = tarjeta
        
        self.object.save()

        return super().form_valid(form)
    
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
        
        tarjeta = transaccion.tarjeta

        with transaction.atomic():
            if transaccion.concepto == "CARGA SALDO":
                tarjeta.saldo -= transaccion.monto
            else:
                tarjeta.saldo += transaccion.monto
            
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
                self.object.monto = 0
                self.object.save()

                tarjetas = Tarjeta.objects.filter(
                    cliente__usuario=self.request.user,
                    habilitada = True
                ).select_related('cliente')

                monto_total_cargado = 0

                for tarjeta in tarjetas:
 
                    input_name = f"monto_{tarjeta.id}"
                    monto = self.request.POST.get(input_name)
                    if monto and float(monto) > 0:
                        DetalleCarga.objects.create(
                            solicitud=self.object,
                            tarjeta=tarjeta,
                            monto=monto
                        )
                        monto_total_cargado += float(monto)
                
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

                monto_total_cargado = 0

                for tarjeta in tarjetas:

                    input_name = f"monto_{tarjeta.id}"
                    monto = self.request.POST.get(input_name)
                    if monto and float(monto) > 0:
                        DetalleCarga.objects.create(
                            solicitud=self.object,
                            tarjeta=tarjeta,
                            monto=monto
                        )
                        monto_total_cargado += float(monto)
                
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
class SolicitudDeCargaDeleteView(LoginRequiredMixin, DeleteView):
    model = SolicitudCarga
    template_name = "transacciones/confirmar_eliminar_carga_de_saldo.html"
    context_object_name= "solicitud"
    success_url = reverse_lazy("lista_solicitudes")

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
                        Transaccion.objects.create(
                            tarjeta=detalle.tarjeta,
                            concepto="CARGA SALDO",
                            monto=detalle.monto,
 
                        )
                        
                        detalle.tarjeta.saldo += detalle.monto
                        detalle.tarjeta.save()
                
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