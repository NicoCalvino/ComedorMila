from django.contrib import admin
from comedor.models import *
# Register your models here.

#admin.site.register(Alumna)
#admin.site.register(Tarjeta)
#admin.site.register(Producto)

@admin.register(Precio)
class PrecioAdmin(admin.ModelAdmin):
    list_display = ("colegio", "nivel", "alm_por_sem", "nro_de_cliente", "precio")
    list_display_links = ("nivel", "alm_por_sem", "nro_de_cliente", "precio")
    search_fields = ("colegio", "nivel", "alm_por_sem", "nro_de_cliente", "precio")
    ordering = ("colegio", "nivel", "alm_por_sem", "nro_de_cliente", "precio")
    list_filter = ("colegio", "nivel", "alm_por_sem", "nro_de_cliente",)

@admin.register(ValeMensual)
class ValeMensualAdmin(admin.ModelAdmin):
    list_display = ("cliente", "usuario", "comentarios")
    list_display_links = ("cliente", "usuario")
    search_fields = ("cliente", "usuario", "comentarios")
    ordering = ("usuario", "cliente")

@admin.register(ValeDiario)
class ValeDiarioAdmin(admin.ModelAdmin):
    list_display = ("cliente", "usuario", "fecha", "comentarios","cancelado")
    list_display_links = ("cliente", "usuario","fecha")
    search_fields = ("cliente", "usuario", "comentarios","fecha")
    ordering = ("fecha", "usuario", "cliente")

@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "cliente", "asistio")
    list_display_links = ("fecha", "cliente")
    search_fields = ("cliente","fecha")
    ordering = ("fecha", "cliente")
    list_filter = ("fecha",)