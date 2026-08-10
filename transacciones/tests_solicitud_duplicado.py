from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from kiosco.models import Tarjeta
from transacciones.models import SolicitudCarga, DetalleCarga

# Middleware mínimo para tests: sin OTP ni axes ni SSL redirect, igual que en tests.py.
TEST_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEST_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]


def _comprobante():
    # FileField con FileExtensionValidator: solo valida la extensión, no el
    # contenido, así que un PNG "falso" alcanza para el test.
    return SimpleUploadedFile(
        "comprobante.png", b"contenido-de-prueba", content_type="image/png"
    )


@override_settings(
    MIDDLEWARE=TEST_MIDDLEWARE,
    AUTHENTICATION_BACKENDS=TEST_BACKENDS,
    SECURE_SSL_REDIRECT=False,
)
class SolicitudCargaDobleEnvioTests(TestCase):
    """El padre envía una solicitud de carga; un doble clic no debe duplicarla."""

    def setUp(self):
        self.colegio = Colegio.objects.create(nombre="Colegio Test")
        self.curso = Curso.objects.create(curso="1A", colegio=self.colegio, nivel="PRIMARIA")
        self.padre = Perfil.objects.create_user(
            email="padre@test.com", password="Passw0rd!123", first_name="Pa", last_name="Dre")
        self.cliente = Cliente.objects.create(
            usuario=self.padre, nombre="Alu", apellido="Mna", curso=self.curso, limite=Decimal("2000"))
        # El signal crea la tarjeta automáticamente (habilitada por defecto).
        self.tarjeta = Tarjeta.objects.get(cliente=self.cliente)
        self.client.force_login(self.padre)

    def _post(self):
        return self.client.post(
            reverse("solicitud_de_carga"),
            {f"monto_{self.tarjeta.id}": "1500", "comprobante": _comprobante()},
        )

    def test_crea_solicitud_ok(self):
        self._post()
        solicitudes = SolicitudCarga.objects.filter(usuario=self.padre)
        self.assertEqual(solicitudes.count(), 1)
        s = solicitudes.first()
        self.assertEqual(s.monto, Decimal("1500"))
        self.assertEqual(s.estado, "PENDIENTE")
        self.assertEqual(DetalleCarga.objects.filter(solicitud=s).count(), 1)

    def test_doble_envio_no_duplica(self):
        self._post()
        self._post()  # segundo clic inmediato: la guardia debe descartarlo
        self.assertEqual(SolicitudCarga.objects.filter(usuario=self.padre).count(), 1)

    def test_sin_monto_no_crea_nada(self):
        # Sin ningún monto > 0 no debe quedar ninguna solicitud ni comprobante huérfano.
        self.client.post(
            reverse("solicitud_de_carga"),
            {f"monto_{self.tarjeta.id}": "0", "comprobante": _comprobante()},
        )
        self.assertEqual(SolicitudCarga.objects.filter(usuario=self.padre).count(), 0)
