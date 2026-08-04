import logging
from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from kiosco.models import *
from comedor.models import CuentaComedor
from comedor.facturacion import facturacion_padre
from comedor.inasistencias import tiene_plan

logger = logging.getLogger(__name__)


def csrf_failure(request, reason=""):
    """Página amable cuando falla la verificación CSRF.

    Reemplaza el cartel técnico por defecto de Django. Además deja registrado en
    el log el motivo exacto que detectó Django (cookie CSRF ausente, token que no
    coincide, referer, etc.) sin necesidad de prender DEBUG en producción, para
    poder confirmar la causa si vuelve a pasar (típico en la PWA instalada en iOS).
    """
    logger.warning(
        "CSRF failure | path=%s | motivo=%s | UA=%s",
        request.path,
        reason,
        request.META.get("HTTP_USER_AGENT", ""),
    )
    return render(request, "main/403_csrf.html", {"reason": reason}, status=403)


# Vistas Básicas
def home(request):
    clientes =  Cliente.objects.none()
    if not request.user.is_authenticated:
        return render(request, "main/index_guest.html")
    
    clientes = Cliente.objects.filter(usuario=request.user)

    if request.user.is_superuser or request.user.is_staff:
        return render(request, "main/index_admin.html")
    
    return render(request, "main/index.html", {'clientes': clientes})


@login_required
def kiosco_familia(request):
    """Sección Kiosco del padre: la grilla de sus alumnos (como el home anterior)."""
    if request.user.is_superuser or request.user.is_staff:
        return redirect('home')

    clientes = Cliente.objects.filter(usuario=request.user)
    return render(request, "main/kiosco_familia.html", {'clientes': clientes})


@login_required
def comedor_familia(request):
    """Sección Comedor del padre: bloque por alumno + costo mensual del comedor.

    El "Saldo Comedor" es el costo mensual del comedor calculado con la misma
    lógica de facturación del admin (días/semana x tabla de precios, con
    descuento familiar), no la suma de saldo de las tarjetas.
    """
    if request.user.is_superuser or request.user.is_staff:
        return redirect('home')

    clientes = list(Cliente.objects.filter(usuario=request.user))
    factura = facturacion_padre(request.user)
    costo_por_hijo = {hijo['cliente'].pk: hijo['subtotal'] for hijo in factura['hijos']}
    for cliente in clientes:
        cliente.costo_comedor = costo_por_hijo.get(cliente.pk, 0)
        cliente.tiene_plan = tiene_plan(cliente)
        cliente.vales_a_favor_disponibles = cliente.vales_a_favor.filter(usado=False)

    cuenta = CuentaComedor.objects.filter(usuario=request.user).first()
    saldo_cuenta = cuenta.saldo if cuenta else 0
    movimientos = list(cuenta.movimientos.all()[:10]) if cuenta else []

    return render(request, "main/comedor_familia.html", {
        'clientes': clientes,
        'saldo_cuenta': saldo_cuenta,
        'costo_estimado': factura['total'],
        'movimientos': movimientos,
    })

@user_passes_test(lambda u: u.is_superuser)
def resultado_importacion(request):
    resumen = request.session.get('ultimo_resultado_importacion')
    
    if not resumen:
        return redirect('lista_usuarios') # O a una página de inicio

    # Limpiamos la sesión después de leerla para que no reaparezca al refrescar.
    request.session.pop('ultimo_resultado_importacion', None)

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
