from django.urls import path
from escuela.views import *
from escuela.views_cuenta_colegio import (
    CuentaColegioView, EditarMovimientoColegioView, EliminarMovimientoColegioView,
    MarcarMesPagadoColegioView, DesmarcarMesPagadoColegioView,
)

urlpatterns = [
    path("home_colegios", EscuelaHomeView.as_view(), name="home_colegios"),

    path("colegios", ColegioListView.as_view(), name="colegios"),
    path("crear_colegio", ColegioCreateView.as_view(), name="crear_colegio"),
    path("eliminar_colegio/<int:pk>", ColegioDeleteView.as_view(), name="eliminar_colegio"),

    path("lista_cursos", CursoListView.as_view(), name="lista_cursos"),
    path("nuevo_curso", NuevoCursoView.as_view(), name="nuevo_curso"),
    path("importar_cursos", ImportarCursosView.as_view(), name="importar_cursos"),
    path("editar_curso/<int:pk>", CursoUpdateView.as_view(), name="editar_curso"),
    path("eliminar_curso/<int:pk>", CursoDeleteView.as_view(), name="eliminar_curso"),

    path("lista_clientes",ListaClientesView.as_view(), name="lista_clientes"),
    path("crear_cliente", CrearClienteView.as_view(), name="crear_cliente"),
    path("importar_clientes", ImportarClientesView.as_view(), name="importar_clientes"),
    path("ver_cliente/<int:pk>",DetalleClienteView.as_view(), name="ver_cliente"),
    path("actualizar_cliente/<int:pk>",ActualizarClienteView.as_view(), name="actualizar_cliente"),
    path("eliminar_cliente/<int:pk>",EliminarClienteView.as_view(), name="eliminar_cliente"),
    path('ajax/cargar-cursos/', CargarCursosView.as_view(), name='ajax_cargar_cursos'),

    path("cuenta_colegio", CuentaColegioView.as_view(), name="cuenta_colegio"),
    path("cuenta_colegio/editar/<int:pk>", EditarMovimientoColegioView.as_view(), name="editar_movimiento_colegio"),
    path("cuenta_colegio/eliminar/<int:pk>", EliminarMovimientoColegioView.as_view(), name="eliminar_movimiento_colegio"),
    path("cuenta_colegio/marcar_pagado", MarcarMesPagadoColegioView.as_view(), name="marcar_mes_pagado_colegio"),
    path("cuenta_colegio/desmarcar_pagado", DesmarcarMesPagadoColegioView.as_view(), name="desmarcar_mes_pagado_colegio"),
]