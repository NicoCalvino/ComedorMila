from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch

class StaffOTPRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Si no está logueado o no es staff, no hacemos nada
        if not request.user.is_authenticated or not request.user.is_staff:
            return self.get_response(request)

        # 2. Si ya pasó el OTP, no hacemos nada
        if request.user.is_verified():
            return self.get_response(request)

        # 3. Definir rutas exentas (Zonas donde NO pedimos OTP)
        bypass_keywords = ['logout', 'verificar-otp', 'static', 'media']
    
        if any(keyword in request.path.lower() for keyword in bypass_keywords):
            return self.get_response(request)

        # 2. Si quieres ser más específico con las rutas de reverse:
        try:
            exempt_urls = [
                reverse('verificar_otp'),
                # Agrega aquí cualquier otra ruta con nombre
            ]
            if any(request.path == url for url in exempt_urls):
                return self.get_response(request)
        except NoReverseMatch:
            pass

        # 4. Verificación de exención
        if any(request.path.startswith(url) for url in exempt_urls):
            return self.get_response(request)

        # 5. Si llegó acá, es Staff no verificado: Redirigir
        return redirect('verificar_otp')