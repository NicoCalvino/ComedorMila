from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from kiosco.models import Tarjeta
from transacciones.models import Transaccion, SolicitudCarga, DetalleCarga

# Middleware mínimo para tests: sin OTP ni axes (que interceptarían al staff/superuser
# antes de llegar a la vista) y sin SSL redirect.
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
class SaldoFlowTests(TestCase):
    """Flujo de dinero: carga, compra, límite de descubierto, edición y borrado."""

    def setUp(self):
        self.colegio = Colegio.objects.create(nombre="Colegio Test")
        self.curso = Curso.objects.create(curso="1A", colegio=self.colegio, nivel="PRIMARIA")
        self.admin = Perfil.objects.create_superuser(
            email="admin@test.com", password="Passw0rd!123", first_name="Ad", last_name="Min")
        self.padre = Perfil.objects.create_user(
            email="padre@test.com", password="Passw0rd!123", first_name="Pa", last_name="Dre")
        self.cliente = Cliente.objects.create(
            usuario=self.padre, nombre="Alu", apellido="Mna", curso=self.curso, limite=Decimal("2000"))
        # El signal crea la tarjeta automáticamente
        self.tarjeta = Tarjeta.objects.get(cliente=self.cliente)
        self.client.force_login(self.admin)

    def _saldo(self):
        self.tarjeta.refresh_from_db()
        return self.tarjeta.saldo

    def test_carga_suma_saldo(self):
        self.client.post(reverse("cargar_saldo"),
                         {"monto": "3500", "numero_tarjeta": self.tarjeta.codigo})
        self.assertEqual(self._saldo(), Decimal("3500"))

    def test_compra_resta_saldo(self):
        self.tarjeta.saldo = Decimal("3500"); self.tarjeta.save()
        self.client.post(reverse("nueva_compra"),
                         {"monto": "1500", "numero_tarjeta": self.tarjeta.codigo})
        self.assertEqual(self._saldo(), Decimal("2000"))

    def test_compra_rechaza_saldo_insuficiente(self):
        self.tarjeta.saldo = Decimal("2000"); self.tarjeta.save()
        # 2000 - 5000 = -3000 < -2000 (límite) -> rechazada
        self.client.post(reverse("nueva_compra"),
                         {"monto": "5000", "numero_tarjeta": self.tarjeta.codigo})
        self.assertEqual(self._saldo(), Decimal("2000"))
        self.assertFalse(Transaccion.objects.filter(concepto="COMPRA").exists())

    def test_compra_permite_descubierto_hasta_limite(self):
        self.tarjeta.saldo = Decimal("2000"); self.tarjeta.save()
        # 2000 - 4000 = -2000, exactamente el límite -> permitida
        self.client.post(reverse("nueva_compra"),
                         {"monto": "4000", "numero_tarjeta": self.tarjeta.codigo})
        self.assertEqual(self._saldo(), Decimal("-2000"))

    def test_compra_respeta_limite_personalizado(self):
        # A5: el límite sale de Cliente.limite, no de un -2000 fijo
        self.cliente.limite = Decimal("500"); self.cliente.save()
        self.tarjeta.saldo = Decimal("100"); self.tarjeta.save()
        # 100 - 700 = -600 < -500 -> rechazada
        self.client.post(reverse("nueva_compra"),
                         {"monto": "700", "numero_tarjeta": self.tarjeta.codigo})
        self.assertEqual(self._saldo(), Decimal("100"))

    def test_compra_tarjeta_inexistente_no_rompe(self):
        # A1: antes lanzaba UnboundLocalError (500); ahora devuelve el form con error (200)
        resp = self.client.post(reverse("nueva_compra"),
                                {"monto": "100", "numero_tarjeta": "999"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "no existe")

    def test_compra_tarjeta_deshabilitada(self):
        self.tarjeta.habilitada = False; self.tarjeta.save()
        resp = self.client.post(reverse("nueva_compra"),
                                {"monto": "100", "numero_tarjeta": self.tarjeta.codigo})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._saldo(), Decimal("0"))

    def test_editar_transaccion_ajusta_saldo(self):
        self.tarjeta.saldo = Decimal("0"); self.tarjeta.save()
        carga = Transaccion.objects.create(
            tarjeta=self.tarjeta, concepto="CARGA SALDO", monto=Decimal("3500"))
        self.tarjeta.saldo = Decimal("3500"); self.tarjeta.save()
        # Editamos la carga 3500 -> 4000; saldo debería subir 500
        self.client.post(reverse("editar_transaccion", kwargs={"id": carga.pk}),
                         {"monto": "4000"})
        self.assertEqual(self._saldo(), Decimal("4000"))

    def test_borrar_transaccion_revierte_saldo(self):
        self.tarjeta.saldo = Decimal("2000"); self.tarjeta.save()
        compra = Transaccion.objects.create(
            tarjeta=self.tarjeta, concepto="COMPRA", monto=Decimal("500"))
        # Borrar una compra devuelve el monto al saldo
        self.client.post(reverse("eliminar_transaccion", args=[compra.pk]))
        self.assertEqual(self._saldo(), Decimal("2500"))
        self.assertFalse(Transaccion.objects.filter(pk=compra.pk).exists())

    def test_aprobar_solicitud_acredita_saldo(self):
        solicitud = SolicitudCarga.objects.create(usuario=self.padre, monto=Decimal("1000"))
        DetalleCarga.objects.create(solicitud=solicitud, tarjeta=self.tarjeta, monto=Decimal("1000"))
        self.client.post(reverse("gestionar_solicitud", kwargs={"code": solicitud.code}),
                         {"accion": "aprobar"})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "APROBADA")
        self.assertEqual(self._saldo(), Decimal("1000"))
        self.assertTrue(Transaccion.objects.filter(tarjeta=self.tarjeta, concepto="CARGA SALDO").exists())

    def test_concepto_display(self):
        # A4: los choices coinciden con el valor almacenado
        carga = Transaccion.objects.create(
            tarjeta=self.tarjeta, concepto="CARGA SALDO", monto=Decimal("1"))
        compra = Transaccion.objects.create(
            tarjeta=self.tarjeta, concepto="COMPRA", monto=Decimal("1"))
        self.assertEqual(carga.get_concepto_display(), "Carga de saldo")
        self.assertEqual(compra.get_concepto_display(), "Compra")


@override_settings(
    MIDDLEWARE=TEST_MIDDLEWARE,
    AUTHENTICATION_BACKENDS=TEST_BACKENDS,
    SECURE_SSL_REDIRECT=False,
)
class SolicitudAccesoTests(TestCase):
    """C2: un usuario no puede borrar la solicitud de otro."""

    def setUp(self):
        self.padre1 = Perfil.objects.create_user(
            email="p1@test.com", password="Passw0rd!123", first_name="P", last_name="Uno")
        self.padre2 = Perfil.objects.create_user(
            email="p2@test.com", password="Passw0rd!123", first_name="P", last_name="Dos")
        self.solicitud = SolicitudCarga.objects.create(usuario=self.padre1, monto=Decimal("100"))

    def test_no_puede_borrar_solicitud_ajena(self):
        self.client.force_login(self.padre2)
        self.client.post(reverse("eliminar_solicitud_de_carga", args=[self.solicitud.pk]))
        self.assertTrue(SolicitudCarga.objects.filter(pk=self.solicitud.pk).exists())
