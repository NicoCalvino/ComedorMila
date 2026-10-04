"""Recaudación diaria en efectivo del kiosco (solo superusuario)."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import Perfil
from kiosco.models import RecaudacionEfectivo

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
class RecaudacionEfectivoTests(TestCase):
    def setUp(self):
        self.admin = Perfil.objects.create_superuser(
            email="admin@t.com", password="x", first_name="Ad", last_name="Min")
        self.padre = Perfil.objects.create_user(
            email="padre@t.com", password="x", first_name="Pa", last_name="Dre")
        self.url = reverse("recaudacion_efectivo")
        self.hoy = date.today()

    def _login_admin(self):
        self.client.force_login(self.admin)

    def test_solo_superusuario(self):
        self.client.force_login(self.padre)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        r = self.client.post(self.url, {"fecha": self.hoy.isoformat(), "monto": "1000"})
        self.assertFalse(RecaudacionEfectivo.objects.exists())

    def test_admin_ve_la_pantalla(self):
        self._login_admin()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Recaudación en efectivo")

    def test_cargar_recaudacion(self):
        self._login_admin()
        r = self.client.post(self.url, {"fecha": self.hoy.isoformat(), "monto": "15250.50", "observaciones": " ok "})
        self.assertEqual(r.status_code, 302)
        reg = RecaudacionEfectivo.objects.get(fecha=self.hoy)
        self.assertEqual(reg.monto, Decimal("15250.50"))
        self.assertEqual(reg.observaciones, "ok")
        self.assertEqual(reg.cargado_por, self.admin)

    def test_fecha_repetida_ofrece_editar(self):
        self._login_admin()
        existente = RecaudacionEfectivo.objects.create(fecha=self.hoy, monto=Decimal("1000"))
        r = self.client.post(self.url, {"fecha": self.hoy.isoformat(), "monto": "2000"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["existente"], existente)
        self.assertContains(r, reverse("editar_recaudacion_efectivo", args=[existente.pk]))
        self.assertEqual(RecaudacionEfectivo.objects.count(), 1)

    def test_no_acepta_fecha_futura(self):
        self._login_admin()
        r = self.client.post(self.url, {"fecha": (self.hoy + timedelta(days=1)).isoformat(), "monto": "1000"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("fecha", r.context["form"].errors)
        self.assertFalse(RecaudacionEfectivo.objects.exists())

    def test_no_acepta_monto_cero_ni_gigante(self):
        self._login_admin()
        for monto in ["0", "-5", "100000000"]:
            r = self.client.post(self.url, {"fecha": self.hoy.isoformat(), "monto": monto})
            self.assertEqual(r.status_code, 200, monto)
            self.assertIn("monto", r.context["form"].errors, monto)
        self.assertFalse(RecaudacionEfectivo.objects.exists())

    def test_editar(self):
        self._login_admin()
        reg = RecaudacionEfectivo.objects.create(fecha=self.hoy, monto=Decimal("1000"))
        url = reverse("editar_recaudacion_efectivo", args=[reg.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(url, {"fecha": self.hoy.isoformat(), "monto": "1500", "observaciones": "corregido"})
        self.assertEqual(r.status_code, 302)
        reg.refresh_from_db()
        self.assertEqual(reg.monto, Decimal("1500"))
        self.assertEqual(reg.observaciones, "corregido")

    def test_eliminar_solo_por_post(self):
        self._login_admin()
        reg = RecaudacionEfectivo.objects.create(fecha=self.hoy, monto=Decimal("1000"))
        url = reverse("eliminar_recaudacion_efectivo", args=[reg.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertTrue(RecaudacionEfectivo.objects.filter(pk=reg.pk).exists())
        r = self.client.post(url)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(RecaudacionEfectivo.objects.filter(pk=reg.pk).exists())

    def test_lista_y_total_del_mes(self):
        self._login_admin()
        RecaudacionEfectivo.objects.create(fecha=date(2026, 8, 3), monto=Decimal("1000"))
        RecaudacionEfectivo.objects.create(fecha=date(2026, 8, 4), monto=Decimal("2500.50"))
        RecaudacionEfectivo.objects.create(fecha=date(2026, 9, 1), monto=Decimal("999"))
        r = self.client.get(self.url + "?mes=2026-08")
        self.assertEqual(len(r.context["registros"]), 2)
        self.assertEqual(r.context["total_mes"], Decimal("3500.50"))
        self.assertEqual(r.context["mes_anterior"], "2026-07")
        self.assertEqual(r.context["mes_siguiente"], "2026-09")

    def test_mes_invalido_usa_el_actual(self):
        self._login_admin()
        r = self.client.get(self.url + "?mes=cualquiera")
        self.assertEqual(r.context["mes_actual"], self.hoy.replace(day=1))
        self.assertIsNone(r.context["mes_siguiente"])
