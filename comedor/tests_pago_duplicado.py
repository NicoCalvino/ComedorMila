from decimal import Decimal
from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import Perfil
from comedor.models import SolicitudPagoComedor

TEST_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEST_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]


def _comprobante():
    # El comprobante del comedor es un ImageField (lo valida Pillow), así que
    # generamos un PNG real con PIL, igual que en tests_pagos.py.
    buf = BytesIO()
    Image.new("RGB", (2, 2), "white").save(buf, "PNG")
    return SimpleUploadedFile("pago.png", buf.getvalue(), content_type="image/png")


@override_settings(
    MIDDLEWARE=TEST_MIDDLEWARE,
    AUTHENTICATION_BACKENDS=TEST_BACKENDS,
    SECURE_SSL_REDIRECT=False,
)
class PagoComedorDobleEnvioTests(TestCase):
    """El padre registra un pago de comedor; un doble clic no debe duplicarlo."""

    def setUp(self):
        # Usuario común (no staff/superuser: la vista redirige a esos al home).
        self.padre = Perfil.objects.create_user(
            email="padre@test.com", password="Passw0rd!123", first_name="Pa", last_name="Dre")
        self.client.force_login(self.padre)

    def _post(self):
        return self.client.post(
            reverse("registrar_pago_comedor"),
            {"monto": "5000", "comprobante": _comprobante()},
        )

    def test_crea_pago_ok(self):
        self._post()
        pagos = SolicitudPagoComedor.objects.filter(usuario=self.padre)
        self.assertEqual(pagos.count(), 1)
        self.assertEqual(pagos.first().monto, Decimal("5000"))
        self.assertEqual(pagos.first().estado, SolicitudPagoComedor.PENDIENTE)

    def test_doble_envio_no_duplica(self):
        self._post()
        self._post()  # segundo clic inmediato: la guardia debe descartarlo
        self.assertEqual(SolicitudPagoComedor.objects.filter(usuario=self.padre).count(), 1)
