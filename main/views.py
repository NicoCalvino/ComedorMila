from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from kiosco.models import *

# Vistas Básicas
def home(request):
    clientes =  Cliente.objects.none()
    if not request.user.is_authenticated:
        return render(request, "main/index_guest.html")
    
    clientes = Cliente.objects.filter(usuario=request.user)

    if request.user.is_superuser or request.user.is_staff:
        return render(request, "main/index_admin.html")
    
    return render(request, "main/index.html", {'clientes': clientes})

@user_passes_test(lambda u: u.is_superuser)
def resultado_importacion(request):
    resumen = request.session.get('ultimo_resultado_importacion')
    
    if not resumen:
        return redirect('lista_usuarios') # O a una página de inicio
    
    # Limpiamos la sesión después de leerla para que no aparezca de nuevo al refrescar
    # del request.session['ultimo_resultado_importacion'] 
    
    return render(request, 'main/resultado_importacion.html', {'resumen': resumen})

def axes_lockout_view(request):
    """Vista personalizada para mostrar cuando una cuenta es bloqueada por Axes."""
    # Retorna la respuesta con un estado HTTP 403 Forbidden
    return render(request, 'main/bloqueo_seguridad.html', status=403)

def verificacion_otp(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.method == "POST":
        token = request.POST.get("otp_token")
        # Buscamos el dispositivo verificado del usuario
        device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
        
        if device and device.verify_token(token):
            otp_login(request, device)
            messages.success(request, f"¡Bienvenido de nuevo, {request.user.email}!")
            return redirect('home') # Cambia 'home' por tu ruta principal
        else:
            messages.error(request, "Código inválido o expirado. Intenta de nuevo.")
    
    return render(request, 'main/otp_custom.html')