from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.views import View
from django.views.generic import ListView,CreateView,UpdateView,DeleteView,FormView
from datetime import timedelta, datetime
import pandas as pd
import os
from django.core.files import File
from menu.models import *
from menu.forms import *
from menu.services import generar_menu_escolar

class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

class FeriadoListView(SuperUserRequiredMixin,ListView):
    model = Feriado
    template_name = "menu/lista_feriados.html"
    context_object_name = "feriados"
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        anio = self.request.GET.get("anio")
        mes = self.request.GET.get("mes")
        nombre = self.request.GET.get("nombre")

        if anio:
            queryset = queryset.filter(fecha__year = anio)
        else:
            queryset = queryset.filter(fecha__year = datetime.now().year)

        if mes:
            queryset = queryset.filter(fecha__month = mes)

        if nombre:
            queryset = queryset.filter(nombre__icontains = nombre)

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_year = datetime.now().year

        context['current_year'] = current_year
        years = []
        for i in range(current_year-2, current_year+3):
            years.append(i)

        context['years'] = years

        return context
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino   

class FeriadoCreateView(SuperUserRequiredMixin, CreateView):
    model = Feriado
    template_name = "menu/crear_feriado.html"
    form_class = FeriadoForm
    
    def get_success_url(self):
        if '_addanother' in self.request.POST:
            messages.success(self.request, 'Feriado creado exitosamente! Puedes cargar el siguiente.', 
                extra_tags='mensaje_local' )
            return reverse_lazy('crear_feriado')    
        
        return reverse_lazy("lista_feriados")

class PlatoListView(SuperUserRequiredMixin, ListView):
    model = Plato
    template_name = "menu/lista_platos.html"
    context_object_name = "platos"
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        nombre = self.request.GET.get("nombre")
        categoria = self.request.GET.get("categoria")
        ingrediente = self.request.GET.get("ingrediente")
        dia_fijo = self.request.GET.get("dia_fijo")

        if nombre:
            queryset = queryset.filter(nombre__icontains = nombre)

        if categoria:
            queryset = queryset.filter(categoria = categoria)

        if ingrediente:
            queryset = queryset.filter(ingrediente_principal = ingrediente)

        if dia_fijo:
            queryset = queryset.filter(dia_fijo = dia_fijo)

        return queryset
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class PlatoCreateView(SuperUserRequiredMixin, CreateView):
    model = Plato
    template_name = "menu/crear_plato.html"
    form_class = PlatoForm
    
    def get_success_url(self):
        if '_addanother' in self.request.POST:
            messages.success(self.request, '¡Plato creado exitosamente! Puedes cargar el siguiente.', 
                extra_tags='mensaje_local' )
            return reverse_lazy('crear_plato')    
        
        return reverse_lazy("lista_platos")
    
class PlatoUpdateView(SuperUserRequiredMixin, UpdateView):
    model = Plato
    template_name = "menu/crear_plato.html"
    form_class = PlatoForm
    
    def get_success_url(self):        
        return reverse_lazy("lista_platos")
    
class PlatoDeleteView(SuperUserRequiredMixin, DeleteView):
    model = Plato
    template_name = "menu/eliminar_plato.html"
    success_url = reverse_lazy("lista_platos")

class MenuListView(SuperUserRequiredMixin, ListView):
    model = Menu
    template_name = "menu/home.html"
    context_object_name = "menus"

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.order_by('-fecha')
        return queryset
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class MenuCalendarView(LoginRequiredMixin, ListView):
    model = Menu
    template_name = "menu/calendar_view.html"
    context_object_name = "menues"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # Traemos todos los feriados de una vez para evitar consultas en el bucle
        feriados_dict = {f.fecha: f for f in Feriado.objects.all()}
        # Traemos todos los menús del rango de fechas necesario
        menus_dict = {m.fecha: m for m in queryset}

        hoy = datetime.today().date()
        inicio_base = hoy - timedelta(days=hoy.weekday())
        
        resultado = []

        # Iteramos por las 3 semanas
        for semana_idx in range(4):
            semana_actual = []
            inicio_semana = inicio_base + timedelta(weeks=semana_idx)
            
            # Iteramos por los 5 días laborales
            for i in range(5):
                fecha_iterada = inicio_semana + timedelta(days=i)
                semana_actual.append({
                    "fecha": fecha_iterada,
                    "menu": menus_dict.get(fecha_iterada),
                    "feriado": feriados_dict.get(fecha_iterada)
                })
            
            resultado.append(semana_actual)
        
        context['semanas'] = resultado
        context['hoy'] = datetime.today().date()
        return context
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class MenuCreateView(SuperUserRequiredMixin, CreateView):
    model = Menu
    template_name = "menu/crear_menu.html"
    form_class = MenuForm

    def get_success_url(self):
        if '_addanother' in self.request.POST:
            messages.success(self.request, '¡Menu creado exitosamente! Puedes cargar el siguiente.', 
                extra_tags='mensaje_local' )
            return reverse_lazy('crear_menu')    
        
        return reverse_lazy("home_menu")
    
class MenuUpdateView(SuperUserRequiredMixin, UpdateView):
    model = Menu
    template_name = "menu/crear_menu.html"
    form_class = MenuForm

    def get_success_url(self): 
        return reverse_lazy('home_menu') 

class MenuFormView(SuperUserRequiredMixin, FormView):
    template_name = 'menu/generacion_menu.html'
    form_class = GeneracioMenuForm
    success_url = reverse_lazy('home_menu') # A donde va tras terminar

    def form_valid(self, form):
        fecha_input = form.cleaned_data['fecha_inicial']
        cant_semanas = form.cleaned_data['semanas']
        
        # 1. Normalizar al Lunes de esa semana (si el usuario eligió un Miércoles)
        fecha_inicio_lunes = fecha_input - timedelta(days=fecha_input.weekday())
        
        # 2. Calcular fecha de fin (Viernes de la última semana elegida)
        fecha_fin = fecha_inicio_lunes + timedelta(weeks=cant_semanas - 1, days=4)

        # 3. Limpiar menús existentes en ese rango (para que se "pisen")
        Menu.objects.filter(fecha__range=[fecha_inicio_lunes, fecha_fin]).delete()

        # 4. Ejecutar el proceso (multiplicamos semanas * 5 días laborales)
        # Adaptamos tu servicio para que genere exactamente los días de ese rango
        generar_menu_escolar(fecha_inicio_lunes, cant_semanas)
        
        return super().form_valid(form)
    
class ImportarMenuView(SuperUserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('archivo_excel')

        if not excel_file or not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Por favor, sube un archivo Excel válido.")
            return redirect('home_menu')
        
        try:
            df = pd.read_excel(excel_file)
            df = df.fillna('') # Evitar errores de NaN con strings
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')

            resultados = {
                'exitos': 0,
                'errores': [],
                'total': len(df),
                'proceso': 'Importación de Menues',
                'url_retorno': 'home_menu'
            }

            for index, row in df.iterrows():
                # Limpieza de datos básica
                fecha = row['fecha'].date()
                dia = str(row.get('dia', '')).strip()
                plato_principal = str(row.get('plato_principal', '')).strip()
                plato_alternativo = str(row.get('plato_alternativo', '')).strip()
                postre = str(row.get('postre', '')).strip()
                
                traduccion_dias = {
                    0: "LUNES",
                    1: "MARTES",
                    2: "MIERCOLES",
                    3: "JUEVES",
                    4: "VIERNES",
                }

                dia = traduccion_dias.get(self.fecha.weekday())

                try:
                    plato_principal_obj = Plato.objects.get(nombre=plato_principal)
                    plato_alternativo_obj = Plato.objects.get(nombre=plato_alternativo)
                    postre_obj = Plato.objects.get(nombre=postre)

                    if not plato_alternativo_obj:
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': f"{plato_principal}",
                            'mensaje': "No se encontró el plato en el sistema"
                        })
                        continue

                    if not postre_obj:
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': f"{plato_principal}",
                            'mensaje': "No se encontró el postre en el sistema"
                        })
                        continue

                    if Menu.objects.filter(
                        fecha=fecha,
                        ).exists():
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': f"{dia} {fecha}",
                            'mensaje': "Ya existe un vale creado para este día"
                        })
                        continue
                    
                    Menu.objects.create(
                        fecha=fecha,
                        dia=dia,
                        plato_principal=plato_principal_obj,
                        plato_alternativo=plato_alternativo_obj,
                        postre=postre_obj,
                    )

                    resultados['exitos'] += 1
                
                except Exception as e:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': f"{dia} {fecha}",
                        'mensaje': str(e)
                    })

            request.session['ultimo_resultado_importacion'] = resultados
            return redirect('resultado_importacion')

        except Exception as e:
            messages.error(request, f"Error crítico: {e}")
            return redirect('home_menu')
    
    def get(self, request, *args, **kwargs):
        return redirect('home_menu')
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino