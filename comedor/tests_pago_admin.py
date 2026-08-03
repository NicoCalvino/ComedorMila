from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import CuentaComedor, MovimientoComedor, SolicitudPagoComedor
from comedor.forms import RegistrarPagoAdminComedorForm

MB = 'django.contrib.auth.backends.ModelBackend'
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']


def _png():
    buf = BytesIO()
    Image.new('RGB', (2, 2), 'white').save(buf, 'PNG')
    return SimpleUploadedFile('c.png', buf.getvalue(), content_type='image/png')


@override_settings(MIDDLEWARE=_MW_SIN_OTP)
class RegistrarPagoAdminComedorTest(TestCase):
    def setUp(self):
        # Familia (padre) con un hijo, para que aparezca en el listado.
        self.padre = Perfil.objects.create_user(
            email="padre@t.com", password="x", first_name="Ana", last_name="Perez")
        self.admin = Perfil.objects.create_user(
            email="admin@t.com", password="x", first_name="Super", last_name="User",
            is_superuser=True, is_staff=True)
        col = Colegio.objects.create(nombre="Mila")
        curso = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        self.hijo = Cliente.objects.create(
            usuario=self.padre, nombre="Beto", apellido="Perez", curso=curso)
        # Cuenta con deuda de 100000.
        self.cuenta = CuentaComedor.para(self.padre)
        self.cuenta.agregar_movimiento(
            MovimientoComedor.CARGO_MENSUAL, Decimal("100000"), periodo="2026-08")

    def _login_admin(self):
        c = Client()
        c.force_login(self.admin, backend=MB)
        return c

    def test_admin_carga_pago_baja_saldo(self):
        c = self._login_admin()
        r = c.post(reverse('registrar_pago_admin_comedor'), {
            'familia': self.padre.pk, 'monto': '30000',
        })
        self.assertRedirects(r, reverse('gestion_pagos_comedor'), fetch_redirect_response=False)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("70000.00"))  # 100000 - 30000
        sol = SolicitudPagoComedor.objects.get(usuario=self.padre)
        self.assertEqual(sol.estado, SolicitudPagoComedor.APROBADO)
        self.assertEqual(sol.resuelto_por, self.admin)
        self.assertIsNotNone(sol.movimiento)
        self.assertEqual(sol.movimiento.tipo, MovimientoComedor.PAGO)
        self.assertEqual(sol.movimiento.monto, Decimal("-30000.00"))

    def test_sin_comprobante_funciona(self):
        c = self._login_admin()
        c.post(reverse('registrar_pago_admin_comedor'), {'familia': self.padre.pk, 'monto': '50000'})
        sol = SolicitudPagoComedor.objects.get(usuario=self.padre)
        self.assertEqual(sol.estado, SolicitudPagoComedor.APROBADO)
        self.assertFalse(sol.comprobante)  # opcional: quedó vacío

    def test_con_comprobante_se_guarda(self):
        c = self._login_admin()
        c.post(reverse('registrar_pago_admin_comedor'), {
            'familia': self.padre.pk, 'monto': '20000', 'comprobante': _png(),
        })
        sol = SolicitudPagoComedor.objects.get(usuario=self.padre)
        self.assertTrue(sol.comprobante)  # se guardó la foto

    def test_monto_invalido_no_registra(self):
        c = self._login_admin()
        r = c.post(reverse('registrar_pago_admin_comedor'), {'familia': self.padre.pk, 'monto': '0'})
        self.assertEqual(r.status_code, 200)  # re-muestra el form con error
        self.assertFalse(SolicitudPagoComedor.objects.exists())
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("100000.00"))

    def test_familia_requerida(self):
        c = self._login_admin()
        r = c.post(reverse('registrar_pago_admin_comedor'), {'monto': '10000'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SolicitudPagoComedor.objects.exists())

    def test_no_admin_no_accede(self):
        c = Client()
        c.force_login(self.padre, backend=MB)  # familia común, no admin
        r = c.post(reverse('registrar_pago_admin_comedor'), {'familia': self.padre.pk, 'monto': '30000'})
        self.assertNotEqual(r.status_code, 200)  # redirigido / denegado
        self.assertFalse(SolicitudPagoComedor.objects.exists())
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("100000.00"))

    def test_solo_familias_con_hijos_en_el_listado(self):
        # Un perfil sin hijos no debe ser elegible; el admin tampoco.
        Perfil.objects.create_user(email="solo@t.com", password="x", first_name="Sin", last_name="Hijos")
        qs = RegistrarPagoAdminComedorForm().fields['familia'].queryset
        self.assertIn(self.padre, qs)
        self.assertNotIn(self.admin, qs)
        self.assertEqual(qs.filter(email="solo@t.com").count(), 0)
