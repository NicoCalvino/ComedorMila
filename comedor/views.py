from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.views.generic import ListView, DeleteView, DetailView, UpdateView, CreateView, TemplateView
from django.db.models import Q, F, IntegerField
from django.db.models.functions import Cast
import pandas as pd
from comedor.models import *
from comedor.forms import *
from escuela.models import Cliente, Colegio
from users.models import Perfil
from datetime import date, datetime, timedelta
import os
from django.core.files import File
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
import json

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
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('ver_cliente', kwargs={'pk': self.kwargs['pk']})
    
class ActualizarValeMensualView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ValeMensual
    template_name = "comedor/vale_mensual.html"
    form_class = ValeMensualForm

    def test_func(self):
        if self.request.user.is_superuser:
            return True
        
        vale_mensual = self.get_object()
        
        return vale_mensual.usuario == self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cliente = get_object_or_404(Cliente, pk=self.kwargs['pk'])
        context['cliente'] = cliente

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
        return reverse_lazy('ver_cliente', kwargs={'pk': self.object.cliente.pk})
    
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
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('ver_cliente', kwargs={'pk': self.kwargs['pk']})
    
class CancelarValeDiarioView(LoginRequiredMixin, View):
    
    def post(self, request, pk):
        vale = get_object_or_404(ValeDiario, pk=pk)
        vale.cancelado = True
        vale.save()
        
        return redirect('ver_cliente', pk=vale.cliente.pk)
    
class HistorialValesDiariosView(LoginRequiredMixin, ListView):
    model = ValeDiario
    template_name = "comedor/historial_vales_diarios.html"
    context_object_name = "vales"

    def get_queryset(self):
        cliente_id = self.kwargs.get('pk')
        return ValeDiario.objects.filter(cliente_id=cliente_id).order_by('-fecha')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasamos el cliente al HTML para poder poner su nombre en el título
        context['cliente'] = get_object_or_404(Cliente, pk=self.kwargs.get('pk'))
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

                ruta_completa = os.path.join(r"C:\Users\Nicolas\Pictures", comprobante)

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


def marcar_asistencia_ajax(request, pk):
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