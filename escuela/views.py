from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DeleteView, DetailView, UpdateView, CreateView, TemplateView
from django.db.models import Q
import pandas as pd
from escuela.forms import *
from escuela.models import *
from users.models import Perfil

# Create your views here.
class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

class ClienteOwnerRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        cliente = self.get_object()
        return self.request.user.is_superuser or cliente.usuario == self.request.user

    def handle_no_permission(self):
        messages.error(self.request, 'No tienes permiso para realizar esta acción.')
        return redirect('home')

class EscuelaHomeView(SuperUserRequiredMixin, TemplateView):
    template_name = "escuela/home.html"

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Vistas de Escuelas
class ColegioListView(SuperUserRequiredMixin, ListView):
    model = Colegio
    template_name = "escuela/colegios.html"
    context_object_name = "colegios"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class ColegioCreateView(SuperUserRequiredMixin, CreateView):
    model = Colegio
    template_name = "escuela/colegios.html"
    form_class = ColegioForm
    success_url = reverse_lazy("colegios")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Esto asegura que 'colegios' esté disponible incluso si el form falla
        context["colegios"] = Colegio.objects.all()
        return context
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class ColegioDeleteView(SuperUserRequiredMixin, DeleteView):
    model = Colegio
    template_name = "escuela/colegios.html"
    success_url = reverse_lazy("colegios")

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Vistas de Cursos

class CursoListView(SuperUserRequiredMixin, ListView):
    model = Curso
    template_name = "escuela/lista_cursos.html"
    context_object_name = "cursos"
    
    def get_queryset(self):
        queryset = super().get_queryset()
        colegio_id = self.request.GET.get("colegio")
        nivel = self.request.GET.get("nivel")
        curso = self.request.GET.get("curso")
        orden = self.request.GET.get('order')
        
        columnas_validas = [
            'curso', '-curso', 
            'colegio', '-colegio', 
            'nivel', '-nivel',
        ]
        
        if orden in columnas_validas:
            queryset = queryset.order_by(orden)
        else:
            queryset = queryset.order_by('nivel','curso')

        if colegio_id:
            queryset = queryset.filter(
                colegio = colegio_id
            )

        if nivel:
            queryset = queryset.filter(
                nivel__icontains = nivel
            )

        if curso:
            queryset = queryset.filter(
                curso__icontains = curso
            )

        return queryset
    
    def get_context_data(self, **kwargs):
        # Llamamos a la implementación base para obtener el contexto
        context = super().get_context_data(**kwargs)
        
        # Agregamos la lista de colegios para llenar el <select> del filtro
        context['colegios_list'] = Colegio.objects.all().order_by('nombre')
        
        return context
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class NuevoCursoView(SuperUserRequiredMixin, CreateView):
    model = Curso
    template_name = "escuela/nuevo_curso.html"
    form_class = CursoForm
    context_object_name = "curso"

    def get_success_url(self):
        if '_addanother' in self.request.POST:
            messages.success(self.request, '¡Curso creado exitosamente! Puedes cargar el siguiente.', 
                extra_tags='mensaje_local' )
            return reverse_lazy('nuevo_curso')    
        return reverse_lazy("lista_cursos")
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino
    
class CursoUpdateView(SuperUserRequiredMixin, UpdateView):
    model = Curso
    template_name = "escuela/nuevo_curso.html"
    form_class = CursoForm
    slug_field ="code"
    slug_url_kwarg = "code"
    
    def get_success_url(self):
        return reverse_lazy(
            "lista_cursos"
            )
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class CursoDeleteView(SuperUserRequiredMixin, DeleteView):
    model = Curso
    template_name = "escuela/confirm_delete.html"
    success_url = reverse_lazy("lista_cursos")

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

class ImportarCursosView(SuperUserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('archivo_excel')

        if not excel_file or not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Por favor, sube un archivo Excel válido.")
            return redirect('lista_cursos')
        
        try:
            df = pd.read_excel(excel_file)
            df = df.fillna('') # Evitar errores de NaN con strings

            resultados = {
                'exitos': 0,
                'errores': [],
                'total': len(df),
                'proceso': 'Importación de Cursos',
                'url_retorno': 'lista_cursos'
            }

            for index, row in df.iterrows():
                # Limpieza de datos básica
                curso = str(row.get('curso', '')).strip()
                nivel = str(row.get('nivel', '')).strip()
                nombre_colegio = str(row.get('colegio', '')).strip()

                try:
                    colegio_obj = Colegio.objects.get(nombre=nombre_colegio)

                    if Curso.objects.filter(curso=curso, nivel=nivel, colegio=colegio_obj).exists():
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': f"{curso} - {nivel} - {nombre_colegio}",
                            'mensaje': "El curso ya está registrado."
                        })
                        continue

                    Curso.objects.create(
                        curso=curso,
                        nivel=nivel,
                        colegio=colegio_obj,
                    )
                    resultados['exitos'] += 1
                
                except Exception as e:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': f"{curso} - {nivel} - {nombre_colegio}",
                        'mensaje': str(e)
                    })

            request.session['ultimo_resultado_importacion'] = resultados
            return redirect('resultado_importacion')

        except Exception as e:
            messages.error(request, f"Error crítico: {e}")
            return redirect('lista_cursos')
    
    def get(self, request, *args, **kwargs):
        return redirect('lista_cursos')
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Vistas de Clientes
class ListaClientesView(SuperUserRequiredMixin, ListView):
    model = Cliente
    template_name = 'escuela/clientes.html'
    context_object_name = 'clientes'

    def get_queryset(self):
        # Obtenemos el queryset base
        queryset = super().get_queryset()
        
        # Parámetros de búsqueda y orden
        busqueda = self.request.GET.get("nombre")
        orden = self.request.GET.get('orden')

        # Filtro de búsqueda
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | 
                Q(apellido__icontains=busqueda) | 
                Q(usuario__first_name__icontains=busqueda) | 
                Q(usuario__last_name__icontains=busqueda)
            )

        # Lógica de ordenamiento
        mapping_orden = {
            'apellido': 'apellido',
            'curso': 'curso',
            'tutor': 'usuario'
        }
        
        criterio = mapping_orden.get(orden)
        if criterio:
            queryset = queryset.order_by(criterio)

        return queryset
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino
    
class CrearClienteView(LoginRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'escuela/crear_cliente.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        # Este método se ejecuta si el formulario es válido
        # Equivale al if form.is_valid() y cliente.save(commit=False)
        form.instance.usuario = self.request.user
        
        return super().form_valid(form)
    
class DetalleClienteView(LoginRequiredMixin, ClienteOwnerRequiredMixin, DetailView):
    model = Cliente
    template_name = 'escuela/ver_cliente.html'
    context_object_name = 'cliente'

class ActualizarClienteView(LoginRequiredMixin, ClienteOwnerRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = 'escuela/editar_cliente.html'
    context_object_name = 'cliente'

    def get_success_url(self):
        return reverse('ver_cliente', kwargs={'pk': self.object.pk})
    
class EliminarClienteView(LoginRequiredMixin, ClienteOwnerRequiredMixin, DeleteView):
    model = Cliente
    template_name = 'escuela/eliminar_cliente.html'
    success_url = reverse_lazy('home')
    context_object_name = 'cliente'

    def delete(self, request, *args, **kwargs):
        # Opcional: Agregar un mensaje de éxito tras eliminar
        messages.success(self.request, "Cliente eliminado correctamente.")
        return super().delete(request, *args, **kwargs)

class CargarCursosView(ListView):
    model = Curso
    template_name = 'escuela/curso_dropdown_list_options.html'
    context_object_name = 'cursos'

    def get_queryset(self):
        colegio_id = self.request.GET.get('colegio_id')
        if colegio_id:
            return Curso.objects.filter(colegio_id=colegio_id).order_by('nivel', 'curso')
        return Curso.objects.none()

class ImportarClientesView(SuperUserRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('archivo_excel')

        if not excel_file or not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Por favor, sube un archivo Excel válido.")
            return redirect('lista_clientes')
        
        try:
            df = pd.read_excel(excel_file)
            df = df.fillna('') # Evitar errores de NaN con strings

            resultados = {
                'exitos': 0,
                'errores': [],
                'total': len(df),
                'proceso': 'Importación de Cliente',
                'url_retorno': 'lista_clientes'
            }

            for index, row in df.iterrows():
                # Limpieza de datos básica
                username = str(row.get('mail_usuario', '')).strip()
                nombre = str(row.get('nombre', '')).strip()
                apellido = str(row.get('apellido', '')).strip()
                nombre_colegio = str(row.get('colegio', '')).strip()
                nombre_curso = str(row.get('curso', '')).strip()
                
                try:
                    usuario_obj = Perfil.objects.get(email=username)
                    colegio_obj = Colegio.objects.get(nombre=nombre_colegio)
                    curso_obj = Curso.objects.get(curso=nombre_curso, colegio=colegio_obj)
                    
                    if Cliente.objects.filter(usuario=usuario_obj, nombre=nombre, apellido=apellido).exists():
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': f"{nombre} - {apellido}",
                            'mensaje': "El cliente ya está registrado."
                        })
                        continue

                    Cliente.objects.create(
                        usuario=usuario_obj,
                        nombre=nombre,
                        apellido=apellido,
                        curso=curso_obj,
                    )
                    resultados['exitos'] += 1

                except Perfil.DoesNotExist:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': username,
                        'mensaje': "El usuario no existe"
                    })
                except Curso.DoesNotExist:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': f"{nombre_curso} en {nombre_colegio}",
                        'mensaje': "El curso no existe"
                    })
                except Exception as e:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': f"{nombre} - {apellido}",
                        'mensaje': str(e)
                    })
            
            request.session['ultimo_resultado_importacion'] = resultados
            return redirect('resultado_importacion')

        except Exception as e:
            messages.error(request, f"Error crítico: {e}")
            return redirect('lista_clientes')
    
    def get(self, request, *args, **kwargs):
        return redirect('lista_clientes')
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino