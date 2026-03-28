from django.contrib import admin
from escuela.models import *
# Register your models here.

#admin.site.register(Alumna)
#admin.site.register(Tarjeta)
#admin.site.register(Producto)

@admin.register(Colegio)
class ColegioAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    list_display_links = ("nombre",)
    search_fields = ("nombre",)
    ordering = ("nombre",)

@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("curso", "nivel", "colegio")
    list_display_links = ("curso","nivel",)
    search_fields = ("curso","nivel")
    ordering = ("colegio","nivel","curso")
    list_filter = ("nivel",)

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    #Columna visibles en la lista del modelo
    list_display = ("nombre", "apellido", "curso")
    #Columnas con enlaces clickeables para entrar en el detalle
    list_display_links = ("nombre","apellido", )
    #Campos por los que se puede buscar
    search_fields = ("nombre","apellido")
    #Orden por defecto
    ordering = ("apellido","nombre")