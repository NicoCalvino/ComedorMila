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


# --- Cuenta de comedor (circuito separado del kiosco) ---

@admin.register(ConfiguracionComedor)
class ConfiguracionComedorAdmin(admin.ModelAdmin):
    list_display = ("porcentaje_devolucion_inasistencia", "divisor_valor_dia", "actualizado")

    def has_add_permission(self, request):
        # Singleton: no permitir crear más de una fila.
        return not ConfiguracionComedor.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class MovimientoComedorInline(admin.TabularInline):
    model = MovimientoComedor
    extra = 0
    fields = ("fecha", "tipo", "monto", "periodo", "concepto", "registrado_por")
    readonly_fields = ("creado",)
    ordering = ("-fecha", "-id")


@admin.register(CuentaComedor)
class CuentaComedorAdmin(admin.ModelAdmin):
    list_display = ("usuario", "saldo", "actualizado")
    search_fields = ("usuario__email", "usuario__first_name", "usuario__last_name")
    ordering = ("usuario",)
    readonly_fields = ("saldo", "actualizado")
    inlines = [MovimientoComedorInline]


@admin.register(MovimientoComedor)
class MovimientoComedorAdmin(admin.ModelAdmin):
    list_display = ("fecha", "cuenta", "tipo", "monto", "periodo", "concepto")
    list_display_links = ("fecha", "cuenta")
    list_filter = ("tipo", "periodo")
    search_fields = ("cuenta__usuario__email", "concepto")
    ordering = ("-fecha", "-id")


@admin.register(SolicitudPagoComedor)
class SolicitudPagoComedorAdmin(admin.ModelAdmin):
    list_display = ("creado", "usuario", "monto", "estado", "resuelto_en", "resuelto_por")
    list_display_links = ("creado", "usuario")
    list_filter = ("estado",)
    search_fields = ("usuario__email",)
    ordering = ("-creado",)
    actions = ("aprobar_pagos", "rechazar_pagos")

    @admin.action(description="Aprobar pagos seleccionados (descuenta del saldo)")
    def aprobar_pagos(self, request, queryset):
        n = 0
        for sol in queryset:
            if sol.aprobar(request.user):
                n += 1
        self.message_user(request, f"{n} pago(s) aprobado(s).")

    @admin.action(description="Rechazar pagos seleccionados")
    def rechazar_pagos(self, request, queryset):
        n = 0
        for sol in queryset:
            if sol.rechazar(request.user):
                n += 1
        self.message_user(request, f"{n} pago(s) rechazado(s).")


@admin.register(Inasistencia)
class InasistenciaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "cliente", "resultado", "monto_devuelto")
    list_display_links = ("fecha", "cliente")
    list_filter = ("resultado", "fecha")
    search_fields = ("cliente__nombre", "cliente__apellido")
    ordering = ("-fecha",)


@admin.register(ValeAFavor)
class ValeAFavorAdmin(admin.ModelAdmin):
    list_display = ("creado", "cliente", "usado", "fecha_uso")
    list_display_links = ("creado", "cliente")
    list_filter = ("usado",)
    search_fields = ("cliente__nombre", "cliente__apellido")
    ordering = ("-creado",)