from django.contrib import admin
from kiosco.models import *
# Register your models here.

#admin.site.register(Alumna)
#admin.site.register(Tarjeta)
#admin.site.register(Producto)

@admin.register(Tarjeta)
class TarjetaAdmin(admin.ModelAdmin):
    list_display = ("codigo","saldo","fecha_activacion","cliente")
    list_display_links = ("codigo",)
    search_fields = ("codigo","id_cliente")
    #Filtros laterales
    list_filter = ("fecha_activacion",)
    #Orden por defecto
    ordering = ("fecha_activacion","codigo")
    #Campos de solo lectura
    readonly_fields = ("fecha_activacion",)


@admin.register(RecaudacionEfectivo)
class RecaudacionEfectivoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "monto", "observaciones", "cargado_por")
    date_hierarchy = "fecha"
    ordering = ("-fecha",)
    readonly_fields = ("cargado_por", "creado", "modificado")
