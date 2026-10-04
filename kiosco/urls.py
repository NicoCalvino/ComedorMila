from django.urls import path
from kiosco.views import *

urlpatterns = [
    path("home_kiosco", home_kiosco, name="home_kiosco"),

    path("historial_cliente/<int:pk>",historial_cliente,name="historial_cliente"),
    
    path("lista_tarjetas",lista_tarjetas, name="lista_tarjetas"),
    # path("crear_tarjeta", crear_tarjeta, name="crear_tarjeta"),
    # path("crear_tarjetas_masivo", crear_tarjetas_masivo, name="crear_tarjetas_masivo"),
    path("ver_tarjeta/<int:pk>",ver_tarjeta, name="ver_tarjeta"),
    # path("ver_tarjeta/<int:pk>/asociar/", asociar_tarjeta, name="asociar_tarjeta"),
    # path("ver_tarjeta/<int:pk>/asociar/<int:cliente_pk>/", asociar_tarjeta_confirmar, name="asociar_tarjeta_confirmar"),
    path('ver_tarjeta/<int:pk>/cambiar-estado/', cambiar_estado_tarjeta, name='cambiar_estado_tarjeta'),
    path('ver_tarjeta/<int:pk>/cambiar-estado-alumno/', cambiar_estado_tarjeta_alumno, name='cambiar_estado_tarjeta_alumno'),

    path("recaudacion_efectivo", recaudacion_efectivo, name="recaudacion_efectivo"),
    path("recaudacion_efectivo/<int:pk>/editar", editar_recaudacion_efectivo, name="editar_recaudacion_efectivo"),
    path("recaudacion_efectivo/<int:pk>/eliminar", eliminar_recaudacion_efectivo, name="eliminar_recaudacion_efectivo"),
    # path("eliminar_tarjeta/<int:pk>",eliminar_tarjeta, name="eliminar_tarjeta"),
]