import json
from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import ValeDiario, Asistencia

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
class ComedorAccesoTests(TestCase):
    """C1, C3 y C4: control de acceso en asistencia, cancelación e historial de vales."""

    def setUp(self):
        self.colegio = Colegio.objects.create(nombre="Colegio Test")
        self.curso = Curso.objects.create(curso="1A", colegio=self.colegio, nivel="PRIMARIA")
        self.admin = Perfil.objects.create_superuser(
            email="admin@test.com", password="Passw0rd!123", first_name="Ad", last_name="Min")
        self.padre1 = Perfil.objects.create_user(
            email="p1@test.com", password="Passw0rd!123", first_name="P", last_name="Uno")
        self.padre2 = Perfil.objects.create_user(
            email="p2@test.com", password="Passw0rd!123", first_name="P", last_name="Dos")
        self.cliente1 = Cliente.objects.create(
            usuario=self.padre1, nombre="Alu", apellido="Uno", curso=self.curso)
        self.vale = ValeDiario.objects.create(
            usuario=self.padre1, cliente=self.cliente1, fecha=date.today())

    # C1 -----------------------------------------------------------------
    def test_marcar_asistencia_requiere_login(self):
        asis = Asistencia.objects.create(fecha=date.today(), cliente=self.cliente1, asistio=False)
        resp = self.client.post(
            reverse("marcar_asistencia_ajax", args=[asis.pk]),
            data=json.dumps({"asistio": True}), content_type="application/json")
        # Anónimo: nunca debe ejecutar la acción (redirect a login o 403)
        self.assertIn(resp.status_code, (302, 403))
        asis.refresh_from_db()
        self.assertFalse(asis.asistio)

    def test_marcar_asistencia_requiere_superuser(self):
        asis = Asistencia.objects.create(fecha=date.today(), cliente=self.cliente1, asistio=False)
        self.client.force_login(self.padre1)  # usuario común
        resp = self.client.post(
            reverse("marcar_asistencia_ajax", args=[asis.pk]),
            data=json.dumps({"asistio": True}), content_type="application/json")
        self.assertEqual(resp.status_code, 403)
        asis.refresh_from_db()
        self.assertFalse(asis.asistio)

    def test_marcar_asistencia_superuser_ok(self):
        asis = Asistencia.objects.create(fecha=date.today(), cliente=self.cliente1, asistio=False)
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse("marcar_asistencia_ajax", args=[asis.pk]),
            data=json.dumps({"asistio": True}), content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        asis.refresh_from_db()
        self.assertTrue(asis.asistio)

    # C3 -----------------------------------------------------------------
    def test_cancelar_vale_ajeno_prohibido(self):
        self.client.force_login(self.padre2)
        resp = self.client.post(reverse("cancelar_vale_diario", args=[self.vale.pk]))
        self.assertIn(resp.status_code, (302, 403))
        self.vale.refresh_from_db()
        self.assertFalse(self.vale.cancelado)

    def test_cancelar_vale_propio_ok(self):
        self.client.force_login(self.padre1)
        self.client.post(reverse("cancelar_vale_diario", args=[self.vale.pk]))
        self.vale.refresh_from_db()
        self.assertTrue(self.vale.cancelado)

    # C4 -----------------------------------------------------------------
    def test_historial_vales_ajeno_prohibido(self):
        self.client.force_login(self.padre2)
        resp = self.client.get(reverse("historial_vales_diarios", args=[self.cliente1.pk]))
        self.assertIn(resp.status_code, (302, 403))

    def test_historial_vales_propio_ok(self):
        self.client.force_login(self.padre1)
        resp = self.client.get(reverse("historial_vales_diarios", args=[self.cliente1.pk]))
        self.assertEqual(resp.status_code, 200)
