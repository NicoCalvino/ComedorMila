from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from users.models import Perfil
from comedor.models import CuentaComedor, MovimientoComedor, SolicitudPagoComedor
from comedor.forms import SolicitudPagoComedorForm

MB = 'django.contrib.auth.backends.ModelBackend'
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']


def _png():
    buf = BytesIO()
    Image.new('RGB', (2, 2), 'white').save(buf, 'PNG')
    return SimpleUploadedFile('c.png', buf.getvalue(), content_type='image/png')


class PagoComedorTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        self.admin = Perfil.objects.create_user(email="a@t.com", password="x", first_name="S", last_name="U", is_superuser=True, is_staff=True)
        # cuenta con deuda de 100000
        self.cuenta = CuentaComedor.para(self.u)
        self.cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("100000"), periodo="2026-08")

    def _sol(self, monto="30000"):
        return SolicitudPagoComedor.objects.create(usuario=self.u, monto=Decimal(monto))

    def test_aprobar_baja_saldo(self):
        sol = self._sol("30000")
        sol.aprobar(self.admin)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("70000.00"))  # 100000 - 30000
        sol.refresh_from_db()
        self.assertEqual(sol.estado, SolicitudPagoComedor.APROBADO)
        self.assertIsNotNone(sol.movimiento)
        self.assertEqual(sol.movimiento.tipo, MovimientoComedor.PAGO)
        self.assertEqual(sol.movimiento.monto, Decimal("-30000.00"))

    def test_aprobar_idempotente(self):
        sol = self._sol("30000")
        sol.aprobar(self.admin)
        sol.aprobar(self.admin)  # segundo intento no hace nada
        self.assertEqual(MovimientoComedor.objects.filter(tipo=MovimientoComedor.PAGO).count(), 1)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("70000.00"))

    def test_rechazar_no_toca_saldo(self):
        sol = self._sol("30000")
        sol.rechazar(self.admin)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("100000.00"))
        sol.refresh_from_db()
        self.assertEqual(sol.estado, SolicitudPagoComedor.RECHAZADO)
        self.assertFalse(MovimientoComedor.objects.filter(tipo=MovimientoComedor.PAGO).exists())

    def test_form_monto_invalido(self):
        f = SolicitudPagoComedorForm(data={'monto': '0'}, files={'comprobante': _png()})
        self.assertFalse(f.is_valid())
        self.assertIn('monto', f.errors)

    def test_padre_envia_pago(self):
        c = Client(); c.force_login(self.u, backend=MB)
        r = c.post(reverse('registrar_pago_comedor'), {'monto': '30000', 'comprobante': _png()})
        self.assertRedirects(r, reverse('comedor_familia'), fetch_redirect_response=False)
        sol = SolicitudPagoComedor.objects.get(usuario=self.u)
        self.assertEqual(sol.estado, SolicitudPagoComedor.PENDIENTE)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("100000.00"))  # aún sin aprobar

    @override_settings(MIDDLEWARE=_MW_SIN_OTP)
    def test_admin_aprueba_desde_gestion(self):
        sol = self._sol("40000")
        c = Client(); c.force_login(self.admin, backend=MB)
        r = c.post(reverse('gestion_pagos_comedor'), {'pago_id': sol.pk, 'accion': 'aprobar'})
        self.assertEqual(r.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, SolicitudPagoComedor.APROBADO)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("60000.00"))  # 100000 - 40000

    # --- Pago en efectivo -------------------------------------------------

    def test_form_transferencia_exige_comprobante(self):
        f = SolicitudPagoComedorForm(data={'monto': '30000', 'medio_pago': 'TRANSFERENCIA'})
        self.assertFalse(f.is_valid())
        self.assertIn('comprobante', f.errors)

    def test_form_sin_medio_es_transferencia(self):
        f = SolicitudPagoComedorForm(data={'monto': '30000'}, files={'comprobante': _png()})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.cleaned_data['medio_pago'], SolicitudPagoComedor.TRANSFERENCIA)

    def test_padre_envia_pago_en_efectivo_sin_comprobante(self):
        c = Client(); c.force_login(self.u, backend=MB)
        r = c.post(reverse('registrar_pago_comedor'), {'monto': '25000', 'medio_pago': 'EFECTIVO'})
        self.assertRedirects(r, reverse('comedor_familia'), fetch_redirect_response=False)
        sol = SolicitudPagoComedor.objects.get(usuario=self.u)
        self.assertEqual(sol.medio_pago, SolicitudPagoComedor.EFECTIVO)
        self.assertEqual(sol.estado, SolicitudPagoComedor.PENDIENTE)
        self.assertFalse(sol.comprobante)
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("100000.00"))  # aún sin aprobar

    def test_efectivo_descarta_comprobante_adjunto(self):
        f = SolicitudPagoComedorForm(
            data={'monto': '25000', 'medio_pago': 'EFECTIVO'}, files={'comprobante': _png()},
        )
        self.assertTrue(f.is_valid(), f.errors)
        self.assertIsNone(f.cleaned_data['comprobante'])

    def test_aprobar_efectivo_baja_saldo(self):
        sol = SolicitudPagoComedor.objects.create(
            usuario=self.u, monto=Decimal("25000"), medio_pago=SolicitudPagoComedor.EFECTIVO,
        )
        mov = sol.aprobar(self.admin)
        self.assertEqual(mov.concepto, "Pago de comedor (efectivo)")
        self.cuenta.refresh_from_db()
        self.assertEqual(self.cuenta.saldo, Decimal("75000.00"))

    # --- Descripción del pago (admin) -------------------------------------

    def test_descripcion_se_suma_al_concepto(self):
        sol = SolicitudPagoComedor.objects.create(
            usuario=self.u, monto=Decimal("10000"), descripcion="Cuota de agosto",
        )
        mov = sol.aprobar(self.admin)
        self.assertEqual(mov.concepto, "Pago de comedor - Cuota de agosto")

    @override_settings(MIDDLEWARE=_MW_SIN_OTP)
    def test_admin_carga_pago_con_descripcion(self):
        # El selector de familias solo lista perfiles con al menos un alumno.
        from escuela.models import Colegio, Curso, Cliente
        col = Colegio.objects.create(nombre="Col Test")
        cur = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=cur)
        c = Client(); c.force_login(self.admin, backend=MB)
        r = c.post(reverse('registrar_pago_admin_comedor'), {
            'familia': self.u.pk, 'monto': '20000', 'descripcion': '  Pagó la abuela  ',
        })
        self.assertEqual(r.status_code, 302)
        sol = SolicitudPagoComedor.objects.get(usuario=self.u)
        self.assertEqual(sol.descripcion, "Pagó la abuela")
        self.assertEqual(sol.estado, SolicitudPagoComedor.APROBADO)
        self.assertEqual(sol.movimiento.concepto, "Pago de comedor - Pagó la abuela")
