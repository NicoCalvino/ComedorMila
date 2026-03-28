from django.urls import path
from comedor.views import *

urlpatterns = [
    path("home", ComedorHomeView.as_view(), name="comedor_home"),

    path("reporte_diario", ReporteDiarioView.as_view(), name="reporte_diario"),
    path("reporte_mensual", ReporteFacturacionView.as_view(), name="reporte_mensual"),
    path("asistencia_dia", AsistenciaView.as_view(), name="asistencia_dia"),
    path('marcar-asistencia/<int:pk>/', marcar_asistencia_ajax, name='marcar_asistencia_ajax'),

    path("lista_precios", PrecioListView.as_view(), name="lista_precios"),
    path("cargar_precio", CargarPrecioView.as_view(), name="cargar_precio"),
    path("editar_precio/<int:pk>/", PrecioUpdateView.as_view(), name="editar_precio"),
    path("importar_precios/", ImportarPreciosView.as_view(), name="importar_precios"),

    path("comedor_mensual", ComedorMensualView.as_view(), name="comedor_mensual"),
    path("carga_vale_mensual/<int:pk>",CargarValeMensualView.as_view(), name="carga_vale_mensual"),
    path("editar_vale_mensual/<int:pk>",ActualizarValeMensualView.as_view(), name="editar_vale_mensual"),
    path("importar_vales_mensuales", ImportarValesMensualesView.as_view(), name="importar_vales_mensuales"),

    path("lista_vales_diarios",ComedorDiarioView.as_view(), name="lista_vales_diarios"),
    path("carga_vale_diario/<int:pk>",CargarValeDiarioView.as_view(), name="carga_vale_diario"),
    path("cancelar_vale_diario/<int:pk>", CancelarValeDiarioView.as_view(), name="cancelar_vale_diario"),
    path("historial_vale_diario/<int:pk>", HistorialValesDiariosView.as_view(), name="historial_vales_diarios"),
    path("importar_vales_diarios", ImportarValesDiariosView.as_view(), name="importar_vales_diarios"),
]