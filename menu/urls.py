from django.urls import path
from menu.views import *

urlpatterns = [
    path("", MenuListView.as_view(), name="home_menu"),
    path("calendar_view", MenuCalendarView.as_view(), name="calendar_view"),
    path("crear_menu", MenuCreateView.as_view(), name="crear_menu"),
    path("editar_menu/<int:pk>", MenuUpdateView.as_view(), name="editar_menu"),
    path("generacion_menu", MenuFormView.as_view(), name="generacion_menu"),

    path("lista_platos", PlatoListView.as_view(), name="lista_platos"),
    path("crear_plato", PlatoCreateView.as_view(), name="crear_plato"),
    path("editar_plato/<int:pk>", PlatoUpdateView.as_view(), name="editar_plato"),
    path("eliminar_plato/<int:pk>", PlatoDeleteView.as_view(), name="eliminar_plato"),

    path("feriados", FeriadoListView.as_view(), name="lista_feriados"),
    path("crear_feriado", FeriadoCreateView.as_view(), name="crear_feriado")
]