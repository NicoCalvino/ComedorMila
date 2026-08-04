"""Señales relacionadas a la suplantación de usuarios (django-hijack).

Motivo: cuando el admin (staff) suplanta a una familia y luego vuelve a su
cuenta, django-hijack rehace la sesión con `login()`. Eso pierde la marca de
"OTP verificado" que exige `StaffOTPRequiredMiddleware`, y el admin tendría que
volver a tipear el 2FA cada vez que sale de una suplantación.

Como el admin ya verificó su OTP al iniciar sesión (antes de poder suplantar),
no tiene sentido volver a pedírselo. Acá restauramos ese estado en la sesión
reutilizando exactamente el mismo mecanismo que usa `main.views.verificacion_otp`.
"""

from django.dispatch import receiver
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from hijack.signals import hijack_ended


@receiver(hijack_ended)
def restaurar_otp_del_admin(sender, hijacker, hijacked, request, **kwargs):
    """Al volver a la cuenta del admin, re-marca su sesión como OTP-verificada.

    `hijack_ended` se emite DESPUÉS de que django-hijack ya volvió a loguear al
    hijacker, así que `request.session` es la sesión nueva del admin y el
    otp_login persiste. Silencioso si el admin no tiene 2FA configurado.
    """
    if hijacker is None:
        return
    device = TOTPDevice.objects.filter(user=hijacker, confirmed=True).first()
    if device is not None:
        otp_login(request, device)
