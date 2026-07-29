from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


def _normalizar_prefijo(url):
    """Asegura que el prefijo empiece con '/' para comparar contra request.path."""
    if not url:
        return None
    return url if url.startswith("/") else "/" + url


class StaffOTPRequiredMiddleware:
    """
    Obliga a los usuarios staff a verificar su OTP (2FA) antes de acceder al sitio.
    Deja pasar sin verificar: rutas de OTP/login/logout y los archivos estáticos y media.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        # 1. Solo aplica a staff autenticado que todavía no verificó el OTP.
        if not user.is_authenticated or not user.is_staff:
            return self.get_response(request)
        if user.is_verified():
            return self.get_response(request)

        # 2. Prefijos de ruta exentos (comparación por startswith, no por substring).
        exentos = []
        for nombre in ("verificar_otp", "login", "logout"):
            try:
                exentos.append(reverse(nombre))
            except NoReverseMatch:
                pass
        for url in (settings.STATIC_URL, settings.MEDIA_URL):
            prefijo = _normalizar_prefijo(url)
            if prefijo:
                exentos.append(prefijo)

        if any(request.path.startswith(prefijo) for prefijo in exentos):
            return self.get_response(request)

        # 3. Staff no verificado en una ruta protegida: lo mandamos a verificar OTP.
        return redirect("verificar_otp")
