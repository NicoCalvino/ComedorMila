from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from users.views import *

urlpatterns = [
    path("login/", LoginView.as_view(template_name="users/login.html"),name="login"),
    path("logout/", LogoutView.as_view(template_name="users/logout.html"),name="logout"),
    path("confirm_logout", confirmar_logout, name="confirmar_logout"),
    path("lista_usuarios/", lista_usuarios, name="lista_usuarios"),
    path("usuarios/<int:pk>/cambiar-estado/", cambiar_estado_usuario, name="cambiar_estado_usuario"),
    path("importar_usuarios/", importar_usuarios_excel, name="importar_usuarios"),
    path("register/", register, name="register"),
    path("perfil/", perfil_detail, name="perfil_detail"),
    path("perfil/<int:pk>/", perfil_detail, name="perfil_usuarios"),
    path("perfil/change", perfil_change, name="perfil_edit"),
    path('perfil/password/', cambiar_password, name='cambiar_password'),
]