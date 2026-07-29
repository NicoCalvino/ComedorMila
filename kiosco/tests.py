from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from kiosco.models import Tarjeta

TEST_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEST_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]


@override_settings(
    MIDDLEWARE=TEST_MIDDLEWARE,
    AUTHENTICATION_BACKENDS=TEST_BACKENDS,
    SECURE_SSL_REDIRECT=False,
)
class CambiarEstadoTarjetaTests(TestCase):
    """C5: habilitar/deshabilitar tarjeta solo por POST (no por GET)."""

    def setUp(self):
        self.colegio = Colegio.objects.create(nombre="Colegio Test")
        self.curso = Curso.objects.create(curso="1A", colegio=self.colegio, nivel="PRIMARIA")
        self.admin = Perfil.objects.create_superuser(
            email="admin@test.com", password="Passw0rd!123", first_name="Ad", last_name="Min")
        self.padre = Perfil.objects.create_user(
            email="padre@test.com", password="Passw0rd!123", first_name="Pa", last_name="Dre")
        self.cliente = Cliente.objects.create(
            usuario=self.padre, nombre="Alu", apellido="Mna", curso=self.curso)
        self.tarjeta = Tarjeta.objects.get(cliente=self.cliente)

    def test_cambiar_estado_admin_get_rechazado(self):
        self.client.force_login(self.admin)
        estado = self.tarjeta.habilitada
        resp = self.client.get(reverse("cambiar_estado_tarjeta", args=[self.tarjeta.pk]))
        self.assertEqual(resp.status_code, 405)
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.habilitada, estado)  # sin cambios

    def test_cambiar_estado_admin_post_ok(self):
        self.client.force_login(self.admin)
        estado = self.tarjeta.habilitada
        self.client.post(reverse("cambiar_estado_tarjeta", args=[self.tarjeta.pk]))
        self.tarjeta.refresh_from_db()
        self.assertNotEqual(self.tarjeta.habilitada, estado)  # toggled

    def test_cambiar_estado_alumno_get_rechazado(self):
        self.client.force_login(self.padre)
        estado = self.tarjeta.habilitada
        resp = self.client.get(reverse("cambiar_estado_tarjeta_alumno", args=[self.tarjeta.pk]))
        self.assertEqual(resp.status_code, 405)
        self.tarjeta.refresh_from_db()
        self.assertEqual(self.tarjeta.habilitada, estado)

    def test_cambiar_estado_alumno_post_propio_ok(self):
        self.client.force_login(self.padre)
        estado = self.tarjeta.habilitada
        self.client.post(reverse("cambiar_estado_tarjeta_alumno", args=[self.tarjeta.pk]))
        self.tarjeta.refresh_from_db()
        self.assertNotEqual(self.tarjeta.habilitada, estado)


class TarjetaCodigoTests(TestCase):
    """A7: el código admite más de 3 dígitos (antes fallaba con max_length=3)."""

    def test_codigo_largo_valido(self):
        # 4 dígitos (cliente >= 1000) y 15 dígitos (tarjeta física) deben validar
        Tarjeta(codigo="1000").full_clean(exclude=["cliente"])
        Tarjeta(codigo="501364000000003").full_clean(exclude=["cliente"])

    def test_codigo_corto_invalido(self):
        with self.assertRaises(ValidationError):
            Tarjeta(codigo="12").full_clean(exclude=["cliente"])
