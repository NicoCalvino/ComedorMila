"""
URL configuration for kiosco_sole project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django_otp.admin import OTPAdminSite
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from main.views import axes_lockout_view

# Configuramos el admin para que requiera OTP
admin.site.__class__ = OTPAdminSite

urlpatterns = [
    path('gestion-interna-sole/', admin.site.urls),
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path("",include("main.urls")),
    path("kiosco/",include("kiosco.urls")),
    path("productos/",include("productos.urls")),
    path("users/", include("users.urls")),
    path("transacciones/", include("transacciones.urls")),
    path("comedor/", include("comedor.urls")),
    path("escuela/", include("escuela.urls")),
    path("menu/", include("menu.urls")),
    path('acceso-denegado/', axes_lockout_view, name='axes_lockout')
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
