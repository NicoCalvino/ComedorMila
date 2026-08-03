from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView, DeleteView, DetailView, UpdateView, CreateView, TemplateView
from django.db.models import Q, F, IntegerField, Value, DecimalField, Sum
from django.db.models.functions import Cast, Coalesce
from decimal import Decimal
import pandas as pd
from comedor.models import *
from comedor.forms import *
from comedor.cargos import generar_cargos_mensuales
from comedor.exportar import xlsx_response
from escuela.models import Cliente, Colegio
from users.models import Perfil
from datetime import date, datetime, timedelta
import os
from django.conf import settings
from django.core.files import File
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
import json

def _destino_comedor(user):
    """A dónde volver tras una acción de comedor: el padre a su página de
    Comedor; el staff/admin al home del comedor."""
    if user.is_superuser or user.is_staff:
        return reverse_lazy('comedor_home')
    return reverse_lazy('comedor_familia')


class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

class ComedorHomeView(SuperUserRequiredMixin, TemplateView):
    template_name = "comedor/home.html"

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Precios
class PrecioListView(SuperUserRequiredMixin, ListView):
    model = Precio
    template_name = "comedor/lista_precios.html"
    context_object_name = "precios"

    def get_queryset(self):
        return Precio.objects.all().select_related('colegio')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Enviamos todos los colegios para llenar el <select> del filtro
        context['colegios'] = Colegio.objects.all().order_by('nombre') 
        return context
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class CargarPrecioView(SuperUserRequiredMixin, CreateView):
    model = Precio
    template_name = "comedor/nuevo_precio.html"
    form_class = PrecioForm
    context_object_name = "precio"

    def get_success_url(self):
        if '_addanother' in self.request.POST:
            messages.success(self.request, '¡Precio creado exitosamente! Puedes cargar el siguiente.', 
                extra_tags='mensaje_local' )
            return reverse_lazy('cargar_precio')    
        return reverse_lazy("lista_precios")
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class PrecioUpdateView(SuperUserRequiredMixin, UpdateView):
    model = Precio
    template_name = "comedor/nuevo_precio.html"
    form_class = PrecioForm
    
    def get_success_url(self):
        return reverse_lazy(
            "lista_precios"
            )

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino 

class ImportarPreciosView(SuperUserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('archivo_excel')

        if not excel_file or not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Por favor, sube un archivo Excel válido.")
            return redirect('lista_precios')
        
        try:
            df = pd.read_excel(excel_file)
            df = df.fillna('') # Evitar errores de NaN con strings

            resultados = {
                'exitos': 0,
                'errores': [],
                'total': len(df),
                'proceso': 'Importación de Precios',
                'url_retorno': 'lista_precios'
            }

            for index, row in df.iterrows():
                # Limpieza de datos básica
                nombre_colegio = str(row.get('colegio', '')).strip()
                alm_por_sem = str(row.get('alm_por_sem', '')).strip()
                nivel = str(row.get('nivel', '')).strip()
                nro_de_cliente = str(row.get('nro_de_cliente', '')).strip()
                precio = str(row.get('precio', '')).strip()

                try:
                    colegio_obj = Colegio.objects.get(nombre=nombre_colegio)

                    if Precio.objects.filter(
                        alm_por_sem=alm_por_sem, 
                        nivel=nivel, 
                        nro_de_cliente=nro_de_cliente, 
                        colegio=colegio_obj
                        ).exists():
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': f"{nivel} - {alm_por_sem} x sem - hijo nro {nro_de_cliente} - {nombre_colegio}",
                            'mensaje': "El precio ya está registrado."
                        })
                        continue

                    Precio.objects.create(
                        alm_por_sem=alm_por_sem,
                        nro_de_cliente=nro_de_cliente,
                        nivel=nivel,
                        precio=precio,
                        colegio=colegio_obj,
                    )
                    resultados['exitos'] += 1
                
                except Exception as e:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': f"{nivel} - {alm_por_sem} x sem - hijo nro {nro_de_cliente} - {nombre_colegio}",
                        'mensaje': str(e)
                    })

            request.session['ultimo_resultado_importacion'] = resultados
            return redirect('resultado_importacion')

        except Exception as e:
            messages.error(request, f"Error crítico: {e}")
            return redirect('lista_precios')
    
    def get(self, request, *args, **kwargs):
        return redirect('lista_precios')
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Vale Mensual
class ComedorMensualView(SuperUserRequiredMixin, ListView):
    model = ValeMensual
    template_name = "comedor/comedor_mensual.html"
    context_object_name = "vales"

    def get_queryset(self):
        return super().get_queryset()
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class CargarValeMensualView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ValeMensual
    template_name = "comedor/vale_mensual.html"
    form_class = ValeMensualForm
    context_object_name = "vale_mensual"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        
        cliente = get_object_or_404(Cliente, pk=self.kwargs['pk'])

        return cliente.usuario == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = get_object_or_404(Cliente, pk=self.kwargs['pk'])
        context['cliente'] = cliente
        context['volver_url'] = _destino_comedor(self.request.user)
        
        context['precios_escuela_uno'] = Precio.objects.filter(
            nivel="PRIMARIA/SECUNDARIA",
            nro_de_cliente = 1,
            colegio=cliente.curso.colegio
        ).order_by('alm_por_sem')

        context['precios_escuela_dos'] = Precio.objects.filter(
            nivel="PRIMARIA/SECUNDARIA",
            nro_de_cliente = 2,
            colegio=cliente.curso.colegio
        ).order_by('alm_por_sem')

        context['precios_escuela_tres'] = Precio.objects.filter(
            nivel="PRIMARIA/SECUNDARIA",
            nro_de_cliente = 3,
            colegio=cliente.curso.colegio
        ).order_by('alm_por_sem')
        
        context['precios_jardin'] = Precio.objects.filter(
            nivel="JARDIN",
            colegio=cliente.curso.colegio,
        ).order_by('alm_por_sem')

        return context
    
    def form_valid(self, form):
        cliente = get_object_or_404(Cliente, pk=self.kwargs['pk'])

        form.instance.cliente = cliente
        form.instance.usuario = self.request.user # O ajustalo según cómo se llame tu relación de perfil
        # Marca desde cuándo rige este plan (para prorratear el cargo del mes).
        form.instance.vigente_desde = timezone.localdate()

        return super().form_valid(form)

    def get_success_url(self):
        return _destino_comedor(self.request.user)

class ActualizarValeMensualView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ValeMensual
    template_name = "comedor/vale_mensual.html"
    form_class = ValeMensualForm

    def form_valid(self, form):
        # Un cambio de plan reinicia su vigencia (para prorratear el mes en curso).
        form.instance.vigente_desde = timezone.localdate()
        return super().form_valid(form)

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        
        vale_mensual = self.get_object()

        return vale_mensual.usuario == self.request.user

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, 'No tenés permiso para editar ese plan.')
        return redirect('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # El pk de la URL es el de ValeMensual, NO el del Cliente. Usamos el
        # cliente del propio plan para no cargar (ni filtrar) datos de otro cliente.
        cliente = self.object.cliente
        context['cliente'] = cliente
        context['volver_url'] = _destino_comedor(self.request.user)

        context['precios_escuela_uno'] = Precio.objects.filter(
            nivel="PRIMARIA/SECUNDARIA",
            nro_de_cliente = 1,
            colegio=cliente.curso.colegio
        ).order_by('alm_por_sem')

        context['precios_escuela_dos'] = Precio.objects.filter(
            nivel="PRIMARIA/SECUNDARIA",
            nro_de_cliente = 2,
            colegio=cliente.curso.colegio
        ).order_by('alm_por_sem')

        context['precios_escuela_tres'] = Precio.objects.filter(
            nivel="PRIMARIA/SECUNDARIA",
            nro_de_cliente = 3,
            colegio=cliente.curso.colegio
        ).order_by('alm_por_sem')
        
        context['precios_jardin'] = Precio.objects.filter(
            nivel="JARDIN",
            colegio=cliente.curso.colegio,
        ).order_by('alm_por_sem')

        return context

    def get_success_url(self):
        return _destino_comedor(self.request.user)
    
class ImportarValesMensualesView(SuperUserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('archivo_excel')

        if not excel_file or not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Por favor, sube un archivo Excel válido.")
            return redirect('comedor_mensual')
        
        try:
            df = pd.read_excel(excel_file)
            df = df.fillna('') # Evitar errores de NaN con strings

            resultados = {
                'exitos': 0,
                'errores': [],
                'total': len(df),
                'proceso': 'Importación de Vales Mensuales',
                'url_retorno': 'comedor_mensual'
            }

            for index, row in df.iterrows():
                # Limpieza de datos básica
                mail_usuario = str(row.get('mail_usuario', '')).strip()
                nombre_cliente = str(row.get('nombre_cliente', '')).strip()
                apellido_cliente = str(row.get('apellido_cliente', '')).strip()
                lunes = str(row.get('lunes', '')).strip()
                martes = str(row.get('martes', '')).strip()
                miercoles = str(row.get('miercoles', '')).strip()
                jueves = str(row.get('jueves', '')).strip()
                viernes = str(row.get('viernes', '')).strip()
                comentarios = str(row.get('comentarios', '')).strip()

                try:
                    usuario_obj = Perfil.objects.get(email=mail_usuario)
                    cliente_obj = Cliente.objects.get(nombre=nombre_cliente, apellido=apellido_cliente, usuario=usuario_obj)

                    if ValeMensual.objects.filter(
                        usuario=usuario_obj, 
                        cliente=cliente_obj
                        ).exists():
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': f"{nombre_cliente} {apellido_cliente} ({usuario_obj.first_name} {usuario_obj.last_name})",
                            'mensaje': "El cliente ya tiene un vale cargado"
                        })
                        continue
                    
                    lunes_boolean = False
                    martes_boolean = False
                    miercoles_boolean = False
                    jueves_boolean = False
                    viernes_boolean = False

                    if lunes == "X":
                        lunes_boolean = True
                    
                    if martes == "X":
                        martes_boolean = True
                    
                    if miercoles == "X":
                        miercoles_boolean = True

                    if jueves == "X":
                        jueves_boolean = True

                    if viernes == "X":
                        viernes_boolean = True

                    ValeMensual.objects.create(
                        usuario=usuario_obj,
                        cliente=cliente_obj,
                        lunes = lunes_boolean,
                        martes = martes_boolean,
                        miercoles = miercoles_boolean,
                        jueves = jueves_boolean,
                        viernes = viernes_boolean,
                        comentarios=comentarios,
                    )
                    resultados['exitos'] += 1
                
                except Exception as e:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': f"{nombre_cliente} {apellido_cliente} ({usuario_obj.first_name} {usuario_obj.last_name})",
                        'mensaje': str(e)
                    })

            request.session['ultimo_resultado_importacion'] = resultados
            return redirect('resultado_importacion')

        except Exception as e:
            messages.error(request, f"Error crítico: {e}")
            return redirect('comedor_mensual')
    
    def get(self, request, *args, **kwargs):
        return redirect('comedor_mensual')
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Vale Diario
class ComedorDiarioView(SuperUserRequiredMixin,ListView):
    model = ValeDiario
    template_name = "comedor/lista_vales_diarios.html"
    context_object_name = "vales"

    def get_queryset(self):
        return super().get_queryset()
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class CargarValeDiarioView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ValeDiario
    template_name = "comedor/vale_diario.html"
    form_class = ValeDiarioForm
    context_object_name = "vale_diario"

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        cliente = get_object_or_404(Cliente, pk=self.kwargs['pk'])
        return cliente.usuario == self.request.user

    def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs['cliente_id'] = self.kwargs.get('pk')
            return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = get_object_or_404(Cliente, pk=self.kwargs['pk'])
        context['cliente'] = cliente
        context['volver_url'] = _destino_comedor(self.request.user)
        context['fecha_minima'] = date.today().strftime('%Y-%m-%d')

        pj = Precio.objects.filter(
            alm_por_sem=1,
            nivel="JARDIN",
            colegio=cliente.curso.colegio
        ).first()
        context['precio_jardin'] = pj.precio / 4 if pj else 0

        pe = Precio.objects.filter(
            alm_por_sem=1,
            nivel="PRIMARIA/SECUNDARIA",
            colegio=cliente.curso.colegio
        ).first()
        context['precio_escuela'] = pe.precio / 4 if pe else 0

        return context
    
    def form_valid(self, form):
        cliente = get_object_or_404(Cliente, pk=self.kwargs['pk'])

        form.instance.cliente = cliente
        form.instance.usuario = self.request.user # O ajustalo según cómo se llame tu relación de perfil

        response = super().form_valid(form)  # guarda el vale (dispara el cargo del día)

        # Si el padre adjuntó un comprobante al cargar el vale, además lo
        # registramos como un pago pendiente de aprobación, por el valor del día.
        if self.request.FILES.get('comprobante'):
            from comedor.cargos import precio_vale_diario
            monto = precio_vale_diario(cliente)
            if monto > 0:
                SolicitudPagoComedor.objects.create(
                    usuario=self.request.user,
                    monto=monto,
                    comprobante=self.object.comprobante,
                    estado=SolicitudPagoComedor.PENDIENTE,
                )
                messages.info(
                    self.request,
                    "Registramos tu comprobante como un pago pendiente de aprobación."
                )

        return response

    def get_success_url(self):
        return _destino_comedor(self.request.user)
    
class CancelarValeDiarioView(LoginRequiredMixin, View):

    def post(self, request, pk):
        vale = get_object_or_404(ValeDiario, pk=pk)
        # Solo el dueño del cliente (o un superusuario) puede cancelar el vale
        if not request.user.is_superuser and vale.cliente.usuario != request.user:
            raise PermissionDenied
        vale.cancelado = True
        vale.save()

        if request.user.is_superuser or request.user.is_staff:
            return redirect('comedor_home')
        return redirect('comedor_familia')

class HistorialValesDiariosView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ValeDiario
    template_name = "comedor/historial_vales_diarios.html"
    context_object_name = "vales"

    def get_cliente(self):
        return get_object_or_404(Cliente, pk=self.kwargs.get('pk'))

    def test_func(self):
        # Solo el dueño del cliente (o un superusuario) puede ver el historial
        cliente = self.get_cliente()
        return self.request.user.is_superuser or cliente.usuario == self.request.user

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, 'No tienes permiso para ver ese historial.')
        return redirect('home')

    def get_queryset(self):
        cliente_id = self.kwargs.get('pk')
        return ValeDiario.objects.filter(cliente_id=cliente_id).order_by('-fecha')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasamos el cliente al HTML para poder poner su nombre en el título
        context['cliente'] = self.get_cliente()
        context['hoy'] = date.today()
        return context

class ImportarValesDiariosView(SuperUserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('archivo_excel')

        if not excel_file or not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Por favor, sube un archivo Excel válido.")
            return redirect('lista_vales_diarios')
        
        try:
            df = pd.read_excel(excel_file)
            df = df.fillna('') # Evitar errores de NaN con strings
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')

            resultados = {
                'exitos': 0,
                'errores': [],
                'total': len(df),
                'proceso': 'Importación de Vales Diarios',
                'url_retorno': 'lista_vales_diarios'
            }

            for index, row in df.iterrows():
                # Limpieza de datos básica
                mail_usuario = str(row.get('mail_usuario', '')).strip()
                nombre_cliente = str(row.get('nombre_cliente', '')).strip()
                apellido_cliente = str(row.get('apellido_cliente', '')).strip()
                fecha = row['fecha'].date()
                cancelado = str(row.get('cancelado', '')).strip()
                comentarios = str(row.get('comentarios', '')).strip()
                comprobante = str(row.get('comprobante', '')).strip()

                # Carpeta de origen configurable (antes estaba hardcodeada a una
                # ruta de Windows que no existe en el servidor). Si el archivo no
                # está, más abajo simplemente no se adjunta el comprobante.
                ruta_completa = os.path.join(settings.COMPROBANTES_IMPORT_DIR, comprobante) if comprobante else ""

                try:
                    usuario_obj = Perfil.objects.get(email=mail_usuario)
                    cliente_obj = Cliente.objects.get(nombre=nombre_cliente, apellido=apellido_cliente, usuario=usuario_obj)

                    cancelado_boolean = False
                    if cancelado == "X":
                        cancelado_boolean = True

                    if ValeDiario.objects.filter(
                        cliente=cliente_obj,
                        fecha=fecha,
                        cancelado = cancelado_boolean
                        ).exists():
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': f"{nombre_cliente} {apellido_cliente} ({usuario_obj.first_name} {usuario_obj.last_name}) {fecha}",
                            'mensaje': "El cliente ya tiene un vale vigente cargado para esa fecha"
                        })
                        continue
                    
                    nuevo_vale = ValeDiario.objects.create(
                        usuario=usuario_obj,
                        cliente=cliente_obj,
                        fecha=fecha,
                        cancelado=cancelado_boolean,
                        comentarios=comentarios,
                    )

                    if os.path.exists(ruta_completa):
                        with open(ruta_completa, 'rb') as f:
                            # Django copiará el archivo a la ruta definida en 'upload_to'
                            nuevo_vale.comprobante.save(comprobante, File(f), save=False)

                    nuevo_vale.save()
                    resultados['exitos'] += 1
                
                except Exception as e:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': f"{nombre_cliente} {apellido_cliente} ({usuario_obj.first_name} {usuario_obj.last_name})",
                        'mensaje': str(e)
                    })

            request.session['ultimo_resultado_importacion'] = resultados
            return redirect('resultado_importacion')

        except Exception as e:
            messages.error(request, f"Error crítico: {e}")
            return redirect('lista_vales_diarios')
    
    def get(self, request, *args, **kwargs):
        return redirect('lista_vales_diarios')
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Reportes
class ReporteDiarioView(SuperUserRequiredMixin,TemplateView):
    template_name = 'comedor/reporte_diario.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Capturar parámetros de filtrado desde la URL
        filtro_colegio = self.request.GET.get('colegio')
        filtro_nivel = self.request.GET.get('nivel')
        filtro_comentarios = self.request.GET.get('comentarios')
        filtro_origen = self.request.GET.get('origen')
        fecha_str = self.request.GET.get('fecha')

        ahora = timezone.localtime(timezone.now())

        if fecha_str:
            try:
                fecha_consulta = timezone.datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                fecha_consulta = ahora.date()
        else:
            # Lógica original por defecto
            if ahora.hour >= 15:
                fecha_consulta = ahora.date() + timedelta(days=1)
            else:
                fecha_consulta = ahora.date()

        # Ajustar si la fecha cae en fin de semana (opcional para la carga inicial)
        if fecha_consulta.weekday() == 5: # Sábado -> Lunes
            fecha_consulta += timedelta(days=2)
        elif fecha_consulta.weekday() == 6: # Domingo -> Lunes
            fecha_consulta += timedelta(days=1)

        def calcular_fecha_navegacion(fecha_ref, direccion):
            nueva_fecha = fecha_ref + timedelta(days=direccion)
            # 0:Lunes, 5:Sábado, 6:Domingo
            if nueva_fecha.weekday() == 5: # Es Sábado
                nueva_fecha += timedelta(days=2) if direccion > 0 else timedelta(days=-1)
            elif nueva_fecha.weekday() == 6: # Es Domingo
                nueva_fecha += timedelta(days=1) if direccion > 0 else timedelta(days=-2)
            return nueva_fecha

        context['fecha_anterior'] = calcular_fecha_navegacion(fecha_consulta, -1).strftime('%Y-%m-%d')
        context['fecha_siguiente'] = calcular_fecha_navegacion(fecha_consulta, 1).strftime('%Y-%m-%d')
        context['fecha_consulta'] = fecha_consulta
        context['hoy'] = ahora.date()

        # 2. Mapeo de días de la semana para el modelo ValeMensual
        # weekday() devuelve 0 para Lunes, 1 Martes...
        dias_mapeo = {
            0: 'lunes',
            1: 'martes',
            2: 'miercoles',
            3: 'jueves',
            4: 'viernes',
        }
        dia_semana_num = fecha_consulta.weekday()
        nombre_campo_dia = dias_mapeo.get(dia_semana_num)

        lista_asistencia = []

        q_mensual = Q(**{f"{nombre_campo_dia}": True}) if nombre_campo_dia else Q(pk__in=[])
        q_diario = Q(fecha=fecha_consulta, cancelado=False)

        if filtro_colegio:
            q_mensual &= Q(cliente__colegio_id=filtro_colegio)
            q_diario &= Q(cliente__colegio_id=filtro_colegio)

        if filtro_nivel:
            q_mensual &= Q(cliente__curso__nivel=filtro_nivel)
            q_diario &= Q(cliente__curso__nivel=filtro_nivel)

        # 3. Obtener alumnos por Vale Mensual (si no es fin de semana)
        if nombre_campo_dia:
            # Filtramos dinámicamente por el nombre del campo (ej: lunes=True)
            mensuales = ValeMensual.objects.filter(q_mensual).select_related('cliente')
            
            if filtro_origen != 'diario':
                for vale in mensuales:
                    comentario = vale.comentarios or ""
                    # Filtro de comentarios (Lógica: si pide 'si', que no esté vacío)
                    if filtro_comentarios == 'si' and not comentario: continue
                    if filtro_comentarios == 'no' and comentario: continue

                    lista_asistencia.append({
                        'cliente': vale.cliente,
                        'origen': 'Plan Mensual',
                        'comentarios': vale.comentarios
                    })
        
        # 4. Obtener alumnos por Vale Diario
        diarios = ValeDiario.objects.filter(q_diario).select_related('cliente')

        for vale in diarios:
            comentario = vale.comentarios or ""
            # Filtro de comentarios (Lógica: si pide 'si', que no esté vacío)
            if filtro_comentarios == 'si' and not comentario: continue
            if filtro_comentarios == 'no' and comentario: continue
            # Evitar duplicados si el alumno tiene mensual y además sacó diario
            if filtro_origen != 'mensual':
                if not any(item['cliente'] == vale.cliente for item in lista_asistencia):
                    lista_asistencia.append({
                        'cliente': vale.cliente,
                        'origen': 'Vale Diario',
                        'comentarios': vale.comentarios
                    })
        

        # Ordenar por curso o nombre si se desea
        lista_asistencia.sort(key=lambda x: (x['cliente'].curso.nivel,x['cliente'].curso.curso, x['cliente'].nombre))

        context['lista_asistencia'] = lista_asistencia
        context['fecha_consulta'] = fecha_consulta
        return context
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class AsistenciaView(SuperUserRequiredMixin,TemplateView):
    template_name = 'comedor/asistencia_dia.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fecha_str = self.request.GET.get('fecha')
        
        # 1. Determinar fecha (reutiliza tu lógica de ReporteDiario)
        fecha_consulta = timezone.localtime(timezone.now()).date()

        if fecha_consulta.weekday() == 5: # Sábado -> Lunes
            fecha_consulta += timedelta(days=2)
        elif fecha_consulta.weekday() == 6: # Domingo -> Lunes
            fecha_consulta += timedelta(days=1)

        # 2. Verificar si ya existen registros para este día
        asistencias = Asistencia.objects.filter(fecha=fecha_consulta).select_related('cliente__curso')

        if not asistencias.exists() or self.request.GET.get('regenerar') == 'true':
            self.generar_asistencias(fecha_consulta)
            asistencias = Asistencia.objects.filter(fecha=fecha_consulta).select_related('cliente__curso')

        # Ordenar para la lista
        asistencias = asistencias.order_by('cliente__curso__nivel', 'cliente__curso__curso', 'cliente__nombre')
        
        context['asistencias'] = asistencias
        context['fecha_consulta'] = fecha_consulta
        return context

    def generar_asistencias(self, fecha):
        """
        Lógica para volcar los alumnos de vales mensuales y diarios 
        a la tabla de Asistencia.
        """
        alumnos_del_dia = [] # Lista de IDs de clientes
        
        # --- Lógica simplificada de tu ReporteDiario ---
        dias_mapeo = {0: 'lunes', 1: 'martes', 2: 'miercoles', 3: 'jueves', 4: 'viernes'}
        nombre_campo = dias_mapeo.get(fecha.weekday())

        # Mensuales
        if nombre_campo:
            mensuales = ValeMensual.objects.filter(**{nombre_campo: True}).values_list('cliente_id', flat=True)
            alumnos_del_dia.extend(list(mensuales))

        # Diarios
        diarios = ValeDiario.objects.filter(fecha=fecha, cancelado=False).values_list('cliente_id', flat=True)
        alumnos_del_dia.extend(list(diarios))

        # Limpiar duplicados (por si tiene ambos vales)
        alumnos_unicos = set(alumnos_del_dia)

        # Crear registros en Asistencia (usando get_or_create para no duplicar si es regeneración)
        for cliente_id in alumnos_unicos:
            Asistencia.objects.get_or_create(
                fecha=fecha,
                cliente_id=cliente_id,
                defaults={'asistio': False}
            )

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class ReporteFacturacionView(SuperUserRequiredMixin,ListView):
    model = Perfil
    template_name = 'comedor/reporte_mensual.html'
    context_object_name = 'usuarios'

    def get_queryset(self):
        # Traemos solo perfiles que tienen vales mensuales activos
        return Perfil.objects.filter(valemensual__isnull=False).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reporte = []

        for usuario in self.get_queryset():
            # Optimizamos la consulta con select_related para evitar el problema N+1
            vales = ValeMensual.objects.filter(usuario=usuario).select_related(
                'cliente', 'cliente__curso'
            ).order_by('cliente__nombre')
            
            datos_usuario = {
                'padre': usuario,
                'hijos': [],
                'total_padre': 0
            }

            vales = vales.annotate(
                total_dias=Cast(
                    F('lunes') + F('martes') + F('miercoles') + F('jueves') + F('viernes'),
                    output_field=IntegerField()
                )
            ).order_by('-total_dias')


            for indice, vale in enumerate(vales, start=1):
                # Calcular días marcados (sumamos los valores booleanos)
                vale.dias_semana = sum([
                    vale.lunes, vale.martes, vale.miercoles, 
                    vale.jueves, vale.viernes
                ])
                
                if vale.dias_semana == 0:
                    continue

                # Lógica de descuento familiar: tope en el 3er hijo (según tabla de precios)
                nro_hijo_clave = indice if indice <= 3 else 3
                if vale.cliente.curso.nivel == "JARDIN":
                    nro_hijo_clave = 1
                
                # Accedemos a la escuela a través de la relación Cliente -> Curso
                nivel = vale.cliente.curso.nivel
                if nivel == "PRIMARIA" or nivel == "SECUNDARIA":
                    nivel = "PRIMARIA/SECUNDARIA"

                colegio = vale.cliente.curso.colegio
                
                # Buscamos el precio correspondiente en la base de datos
                precio_obj = Precio.objects.filter(
                    alm_por_sem=vale.dias_semana,
                    colegio = colegio,
                    nivel=nivel,
                    nro_de_cliente=nro_hijo_clave
                ).first()
                
                precio_monto = precio_obj.precio if precio_obj else 0

                datos_usuario['hijos'].append({
                    'nombre': f"{vale.cliente.nombre} {vale.cliente.apellido}",
                    'curso': vale.cliente.curso.curso,
                    'colegio':colegio,
                    'nivel': nivel,
                    'dias': vale.dias_semana,
                    'nro_orden': indice,
                    'subtotal': precio_monto
                })
                
                datos_usuario['total_padre'] += precio_monto
                
            if datos_usuario['hijos']:
                reporte.append(datos_usuario)

        context['reporte'] = reporte
        return context
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino


@login_required
@require_POST
def marcar_asistencia_ajax(request, pk):
    # La gestión de asistencia es exclusiva de administradores
    if not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'No autorizado'}, status=403)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            asistencia = Asistencia.objects.get(pk=pk)
            asistencia.asistio = data.get('asistio')
            asistencia.save()

            # Calculamos cuántos hay presentes hoy para actualizar el contador del HTML
            total_presentes = Asistencia.objects.filter(
                fecha=asistencia.fecha, 
                asistio=True
            ).count()

            return JsonResponse({
                'status': 'ok', 
                'total_presentes': total_presentes
            })
        except Asistencia.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Registro no encontrado'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


class GenerarCargosMensualesView(SuperUserRequiredMixin, View):
    """Admin: genera los cargos mensuales de comedor de un período (idempotente)."""
    template_name = 'comedor/generar_cargos.html'

    def get(self, request):
        hoy = timezone.localdate()
        return render(request, self.template_name, {'year': hoy.year, 'month': hoy.month})

    def post(self, request):
        try:
            year = int(request.POST.get('year'))
            month = int(request.POST.get('month'))
            if not (1 <= month <= 12):
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, "Período inválido.")
            return redirect('generar_cargos_mensuales')

        resultado = generar_cargos_mensuales(year, month, registrado_por=request.user)
        messages.success(
            request,
            f"Cargos {resultado['periodo']}: {len(resultado['creados'])} generados, "
            f"{len(resultado['omitidos'])} omitidos. Total $ {resultado['total']}."
        )
        return render(request, self.template_name, {
            'year': year, 'month': month, 'resultado': resultado,
        })

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home')

class RegistrarPagoComedorView(LoginRequiredMixin, CreateView):
    """Padre: registra un pago de comedor subiendo el comprobante. Queda
    pendiente hasta que el admin lo apruebe."""
    model = SolicitudPagoComedor
    form_class = SolicitudPagoComedorForm
    template_name = 'comedor/registrar_pago.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cuenta = CuentaComedor.objects.filter(usuario=self.request.user).first()
        context['saldo'] = cuenta.saldo if cuenta else 0
        return context

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        form.instance.estado = SolicitudPagoComedor.PENDIENTE
        messages.success(self.request, "¡Pago registrado! Queda pendiente de aprobación.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('comedor_familia')


class RegistrarPagoAdminComedorView(SuperUserRequiredMixin, View):
    """Admin: carga un pago de comedor a nombre de una familia (por ejemplo
    cuando mandan el comprobante por WhatsApp). Acredita el saldo al instante,
    sin pasar por el circuito de aprobación, porque lo registra el administrador."""
    template_name = 'comedor/registrar_pago_admin.html'

    def get(self, request):
        initial = {}
        fam_id = request.GET.get('familia')
        if fam_id:
            initial['familia'] = fam_id  # prefill al venir desde el estado de cuenta
        return render(request, self.template_name, {
            'form': RegistrarPagoAdminComedorForm(initial=initial),
        })

    def post(self, request):
        form = RegistrarPagoAdminComedorForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        familia = form.cleaned_data['familia']
        monto = form.cleaned_data['monto']
        comprobante = form.cleaned_data.get('comprobante')

        # Reutiliza el circuito ya probado: se crea la solicitud y se aprueba en
        # el acto (registrado_por = admin). Queda trazable en "Últimos resueltos".
        sol = SolicitudPagoComedor.objects.create(
            usuario=familia,
            monto=monto,
            comprobante=comprobante if comprobante else None,
            estado=SolicitudPagoComedor.PENDIENTE,
        )
        sol.aprobar(request.user)

        cuenta = CuentaComedor.para(familia)
        if cuenta.saldo > 0:
            estado_saldo = f"debe $ {cuenta.saldo:.0f}"
        elif cuenta.saldo < 0:
            estado_saldo = f"tiene a favor $ {abs(cuenta.saldo):.0f}"
        else:
            estado_saldo = "está al día"
        messages.success(
            request,
            f"Pago de $ {monto:.0f} cargado a nombre de {familia}. "
            f"Ahora la cuenta {estado_saldo}.",
        )
        return redirect('gestion_pagos_comedor')

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home')


class GestionPagosComedorView(SuperUserRequiredMixin, View):
    """Admin: lista los pagos pendientes y permite aprobar o rechazar."""
    template_name = 'comedor/gestion_pagos.html'

    def get(self, request):
        pendientes = SolicitudPagoComedor.objects.filter(
            estado=SolicitudPagoComedor.PENDIENTE,
        ).select_related('usuario')
        resueltas = SolicitudPagoComedor.objects.exclude(
            estado=SolicitudPagoComedor.PENDIENTE,
        ).select_related('usuario', 'resuelto_por')[:20]
        return render(request, self.template_name, {
            'pendientes': pendientes, 'resueltas': resueltas,
        })

    def post(self, request):
        sol = get_object_or_404(SolicitudPagoComedor, pk=request.POST.get('pago_id'))
        accion = request.POST.get('accion')
        if accion == 'aprobar':
            sol.aprobar(request.user)
            messages.success(request, f"Pago de {sol.usuario} aprobado. Se descontó del saldo.")
        elif accion == 'rechazar':
            sol.rechazar(request.user)
            messages.info(request, f"Pago de {sol.usuario} rechazado.")
        return redirect('gestion_pagos_comedor')

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home')


class AvisarInasistenciasView(LoginRequiredMixin, View):
    """Padre: avisa una o varias inasistencias (hoy y/o días futuros)."""
    template_name = 'comedor/avisar_inasistencias.html'

    def _cliente(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)
        if not request.user.is_superuser and cliente.usuario != request.user:
            raise PermissionDenied
        return cliente

    def get(self, request, pk):
        cliente = self._cliente(request, pk)
        from comedor.inasistencias import tiene_plan, dias_plan_legibles
        return render(request, self.template_name, {
            'cliente': cliente,
            'tiene_plan': tiene_plan(cliente),
            'dias_plan': dias_plan_legibles(cliente),
            'hoy': timezone.localdate().isoformat(),
        })

    def post(self, request, pk):
        cliente = self._cliente(request, pk)
        from comedor.inasistencias import registrar_inasistencias

        fechas = []
        for s in request.POST.getlist('fechas'):
            s = (s or '').strip()
            if not s:
                continue
            try:
                y, m, d = (int(x) for x in s.split('-'))
                fechas.append(date(y, m, d))
            except (ValueError, TypeError):
                continue
        fechas = list(dict.fromkeys(fechas))  # sin duplicados, conservando orden

        if not fechas:
            messages.error(request, "Elegí al menos un día.")
            return redirect('avisar_inasistencias', pk=cliente.pk)

        res = registrar_inasistencias(cliente, fechas)
        ok = res['ok']
        if ok:
            dev = sum(1 for r in ok if r['resultado'] == Inasistencia.DEVOLUCION)
            vaf = sum(1 for r in ok if r['resultado'] == Inasistencia.VALE_A_FAVOR)
            sin = sum(1 for r in ok if r['resultado'] == Inasistencia.SIN_COMPENSACION)
            partes = []
            if dev:
                partes.append(f"{dev} con devolución de dinero")
            if vaf:
                partes.append(f"{vaf} con almuerzo a favor")
            if sin:
                partes.append(f"{sin} sin compensación (aviso tardío de hoy)")
            messages.success(request, f"Avisaste {len(ok)} inasistencia(s): " + ", ".join(partes) + ".")
        if res['errores']:
            detalle = "; ".join(f"{f:%d/%m/%Y} ({m})" for f, m in res['errores'])
            messages.warning(request, f"No se registraron: {detalle}.")

        return redirect('comedor_familia')


class UsarValeAFavorView(LoginRequiredMixin, View):
    """Padre: usa un almuerzo a favor eligiendo un día futuro."""
    def post(self, request, pk):
        vaf = get_object_or_404(ValeAFavor, pk=pk)
        if not request.user.is_superuser and vaf.cliente.usuario != request.user:
            raise PermissionDenied
        from comedor.inasistencias import usar_vale_a_favor
        fecha_str = request.POST.get('fecha', '')
        try:
            y, m, d = (int(x) for x in fecha_str.split('-'))
            fecha = date(y, m, d)
        except (ValueError, TypeError):
            messages.error(request, "Elegí una fecha válida.")
            return redirect('comedor_familia')
        try:
            usar_vale_a_favor(vaf, fecha, usuario=request.user)
            messages.success(request, f"¡Listo! Almuerzo a favor agendado para el {fecha:%d/%m/%Y}.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('comedor_familia')


class HistorialComedorView(LoginRequiredMixin, ListView):
    """Padre: historial completo de movimientos de su cuenta de comedor."""
    template_name = 'comedor/historial_comedor.html'
    context_object_name = 'movimientos'
    paginate_by = 30

    def _cuenta(self):
        return CuentaComedor.objects.filter(usuario=self.request.user).first()

    def get_queryset(self):
        cuenta = self._cuenta()
        if not cuenta:
            return MovimientoComedor.objects.none()
        return cuenta.movimientos.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cuenta = self._cuenta()
        context['saldo'] = cuenta.saldo if cuenta else 0
        return context


class EstadoCuentaComedorView(SuperUserRequiredMixin, ListView):
    """Admin: estado de cuenta de comedor de todas las familias, con el saldo
    actual de cada una. Ordenado por deuda (las que más deben, primero).
    Se puede buscar por nombre/email y filtrar por estado."""
    template_name = 'comedor/estado_cuentas.html'
    context_object_name = 'familias'
    paginate_by = 40

    def _base_qs(self):
        qs = (Perfil.objects
              .filter(clientes__isnull=False, is_superuser=False)
              .distinct()
              .annotate(saldo_comedor=Coalesce(
                  'cuenta_comedor__saldo',
                  Value(Decimal('0.00')),
                  output_field=DecimalField(max_digits=12, decimal_places=2),
              )))
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
            )
        estado = self.request.GET.get('estado', 'todos')
        if estado == 'deben':
            qs = qs.filter(saldo_comedor__gt=0)
        elif estado == 'afavor':
            qs = qs.filter(saldo_comedor__lt=0)
        elif estado == 'aldia':
            qs = qs.filter(saldo_comedor=0)
        return qs

    def get_queryset(self):
        return self._base_qs().order_by('-saldo_comedor', 'last_name', 'first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        todas = list(self._base_qs())
        context['total_deuda'] = sum((f.saldo_comedor for f in todas if f.saldo_comedor > 0), Decimal('0.00'))
        context['total_favor'] = sum((-f.saldo_comedor for f in todas if f.saldo_comedor < 0), Decimal('0.00'))
        context['cantidad'] = len(todas)
        context['q'] = self.request.GET.get('q', '')
        context['estado'] = self.request.GET.get('estado', 'todos')
        return context

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home')


class EstadoCuentaComedorDetalleView(SuperUserRequiredMixin, ListView):
    """Admin: historial completo de la cuenta de comedor de una familia."""
    template_name = 'comedor/estado_cuenta_detalle.html'
    context_object_name = 'movimientos'
    paginate_by = 30

    def _familia(self):
        return get_object_or_404(Perfil, pk=self.kwargs['pk'])

    def get_queryset(self):
        cuenta = CuentaComedor.objects.filter(usuario=self._familia()).first()
        if not cuenta:
            return MovimientoComedor.objects.none()
        return cuenta.movimientos.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        familia = self._familia()
        cuenta = CuentaComedor.objects.filter(usuario=familia).first()
        context['familia'] = familia
        context['saldo'] = cuenta.saldo if cuenta else Decimal('0.00')
        context['hijos'] = familia.clientes.all()
        return context

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home')


# ---------------------------------------------------------------------------
# Exportación de reportes a Excel (admin)
# ---------------------------------------------------------------------------

class _ExcelBase(SuperUserRequiredMixin, View):
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home')


class ReporteFacturacionExcelView(_ExcelBase):
    def get(self, request):
        vista = ReporteFacturacionView()
        vista.request = request
        vista.kwargs = {}
        vista.object_list = vista.get_queryset()
        ctx = vista.get_context_data(object_list=vista.object_list)
        headers = ['Familia', 'Alumno', 'Colegio', 'Nivel', 'Días/sem', 'Subtotal']
        rows = []
        for fam in ctx['reporte']:
            for hijo in fam['hijos']:
                rows.append([str(fam['padre']), hijo['nombre'], str(hijo['colegio']),
                             hijo['nivel'], hijo['dias'], hijo['subtotal']])
            rows.append([str(fam['padre']), 'TOTAL FAMILIA', '', '', '', fam['total_padre']])
        return xlsx_response('facturacion_comedor.xlsx', headers, rows,
                             'Facturación mensual de comedor')


class ReporteDiarioExcelView(_ExcelBase):
    def get(self, request):
        vista = ReporteDiarioView()
        vista.request = request
        vista.kwargs = {}
        ctx = vista.get_context_data()
        fecha = ctx['fecha_consulta']
        headers = ['Alumno', 'Curso', 'Colegio', 'Nivel', 'Origen', 'Comentarios']
        rows = []
        for item in ctx['lista_asistencia']:
            c = item['cliente']
            rows.append([f"{c.nombre} {c.apellido}", c.curso.curso, str(c.curso.colegio),
                         c.curso.nivel, item['origen'], item.get('comentarios') or ''])
        return xlsx_response(f'reporte_diario_{fecha:%Y-%m-%d}.xlsx', headers, rows,
                             f'Reporte diario de comedor - {fecha:%d/%m/%Y}')


class ComedorMensualExcelView(_ExcelBase):
    _DIAS = [('lunes', 'Lun'), ('martes', 'Mar'), ('miercoles', 'Mié'),
             ('jueves', 'Jue'), ('viernes', 'Vie')]

    def get(self, request):
        headers = ['Alumno', 'Curso', 'Colegio', 'Días', 'Comentarios']
        rows = []
        vales = ValeMensual.objects.select_related(
            'cliente', 'cliente__curso', 'cliente__curso__colegio'
        ).order_by('cliente__curso__nivel', 'cliente__nombre')
        for v in vales:
            dias = ", ".join(lbl for attr, lbl in self._DIAS if getattr(v, attr))
            c = v.cliente
            rows.append([f"{c.nombre} {c.apellido}", c.curso.curso, str(c.curso.colegio),
                         dias, v.comentarios or ''])
        return xlsx_response('comedor_mensual.xlsx', headers, rows,
                             'Planes mensuales de comedor')


class ValesDiariosExcelView(_ExcelBase):
    def get(self, request):
        headers = ['Fecha', 'Alumno', 'Curso', 'Colegio', 'Cancelado', 'Comentarios']
        rows = []
        vales = ValeDiario.objects.select_related(
            'cliente', 'cliente__curso', 'cliente__curso__colegio'
        ).order_by('-fecha')
        for v in vales:
            c = v.cliente
            rows.append([v.fecha, f"{c.nombre} {c.apellido}", c.curso.curso, str(c.curso.colegio),
                         'Sí' if v.cancelado else 'No', v.comentarios or ''])
        return xlsx_response('vales_diarios.xlsx', headers, rows, 'Vales diarios')
