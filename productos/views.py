from django.views.generic import ListView, DeleteView, DetailView, UpdateView, CreateView
from django.shortcuts import redirect
from django.db.models import Q
from django.urls import reverse_lazy
from django.contrib import messages
from productos.models import Producto
from productos.forms import *
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class SuperUserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

# Lista de Productos
class ProductoListView(ListView):
    model = Producto
    template_name = "productos/productos.html"
    context_object_name = "productos"
    
    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("nombre")
        orden = self.request.GET.get('orden')
        
        columnas_validas = [
            'nombre', '-nombre', 
            'marca', '-marca', 
            'categoria', '-categoria', 
            'precio', '-precio'
        ]
        
        if orden in columnas_validas:
            queryset = queryset.order_by(orden)
        else:
            queryset = queryset.order_by('nombre')

        if query:
            queryset = queryset.filter(
                Q(nombre__icontains = query) | Q(marca__icontains=query) | Q(categoria__icontains=query)
            )

        return queryset
    
    

# Detalle de Producto
class ProductoDetailView(LoginRequiredMixin, DetailView):
    model = Producto
    template_name = "productos/ver_producto.html"
    context_object_name = "producto"
    slug_field ="code"
    slug_url_kwarg = "code"

# Creación de Producto
class ProductoCreateView(SuperUserRequiredMixin, CreateView):
    model = Producto
    template_name = "productos/crear_producto.html"
    form_class = ProductoForm

    def get_success_url(self):
        if '_addanother' in self.request.POST:
            messages.success(self.request, '¡Producto creado exitosamente! Puedes cargar el siguiente.', 
                extra_tags='mensaje_local' )
            return reverse_lazy('crear_producto')    
        return reverse_lazy(
            "detalle_producto",
             kwargs={"code":self.object.code}
            )
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Lista de Productos
class ProductoUpdateView(SuperUserRequiredMixin, UpdateView):
    model = Producto
    template_name = "productos/editar_producto.html"
    form_class = ProductoForm
    slug_field ="code"
    slug_url_kwarg = "code"

    def get_success_url(self):
        return reverse_lazy(
            "detalle_producto",
            kwargs={"code":self.object.code}
            )
    
    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino

# Eliminar Producto
class ProductoDeleteView(SuperUserRequiredMixin, DeleteView):
    model = Producto
    template_name = "productos/confirm_delete.html"
    success_url = reverse_lazy("lista_productos")

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect('home') # Cambia 'index' por el nombre de tu URL de destino
