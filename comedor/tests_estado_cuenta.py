from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import CuentaComedor, MovimientoComedor

MB = 'django.contrib.auth.backends.ModelBackend'
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']


@override_settings(MIDDLEWARE=_MW_SIN_OTP)
class EstadoCuentaComedorTest(TestCase):
    def setUp(self):
        self.admin = Perfil.objects.create_user(
            email="admin@t.com", password="x", first_name="Super", last_name="User",
            is_superuser=True, is_staff=True)
        col = Colegio.objects.create(nombre="Mila")
        self.curso = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")

        # Familia que DEBE 50000
        self.deudor = self._familia("deudor@t.com", "Ana", "Deudora")
        CuentaComedor.para(self.deudor).agregar_movimiento(
            MovimientoComedor.CARGO_MENSUAL, Decimal("50000"), periodo="2026-08")

        # Familia A FAVOR 10000 (pagó de más)
        self.afavor = self._familia("afavor@t.com", "Beto", "Afavor")
        CuentaComedor.para(self.afavor).agregar_movimiento(
            MovimientoComedor.PAGO, Decimal("-10000"))

        # Familia con hijo pero SIN actividad de comedor (saldo 0 / al día)
        self.aldia = self._familia("aldia@t.com", "Caro", "Aldia")

    def _familia(self, email, nombre, apellido):
        p = Perfil.objects.create_user(email=email, password="x", first_name=nombre, last_name=apellido)
        Cliente.objects.create(usuario=p, nombre=nombre, apellido=apellido, curso=self.curso)
        return p

    def _cli(self):
        c = Client()
        c.force_login(self.admin, backend=MB)
        return c

    def test_lista_muestra_todas_las_familias_y_totales(self):
        r = self._cli().get(reverse('estado_cuentas_comedor'))
        self.assertEqual(r.status_code, 200)
        # Las 3 familias aparecen, incluso la que nunca usó el comedor.
        self.assertContains(r, "Deudora")
        self.assertContains(r, "Afavor")
        self.assertContains(r, "Aldia")
        self.assertEqual(r.context['cantidad'], 3)
        self.assertEqual(r.context['total_deuda'], Decimal("50000.00"))
        self.assertEqual(r.context['total_favor'], Decimal("10000.00"))

    def test_orden_por_deuda(self):
        r = self._cli().get(reverse('estado_cuentas_comedor'))
        familias = list(r.context['familias'])
        # El deudor (saldo mayor) va primero; la de a favor (saldo negativo) última.
        self.assertEqual(familias[0], self.deudor)
        self.assertEqual(familias[-1], self.afavor)

    def test_filtro_deben(self):
        r = self._cli().get(reverse('estado_cuentas_comedor'), {'estado': 'deben'})
        familias = list(r.context['familias'])
        self.assertIn(self.deudor, familias)
        self.assertNotIn(self.afavor, familias)
        self.assertNotIn(self.aldia, familias)

    def test_busqueda_por_nombre(self):
        r = self._cli().get(reverse('estado_cuentas_comedor'), {'q': 'Deudora'})
        familias = list(r.context['familias'])
        self.assertEqual(familias, [self.deudor])

    def test_detalle_muestra_saldo_y_movimientos(self):
        r = self._cli().get(reverse('estado_cuenta_comedor', args=[self.deudor.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['saldo'], Decimal("50000.00"))
        self.assertEqual(len(r.context['movimientos']), 1)
        self.assertContains(r, "Cargar un pago a esta familia")

    def test_detalle_familia_sin_actividad(self):
        r = self._cli().get(reverse('estado_cuenta_comedor', args=[self.aldia.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['saldo'], Decimal("0.00"))
        self.assertEqual(len(r.context['movimientos']), 0)

    def test_no_admin_no_accede(self):
        c = Client()
        c.force_login(self.deudor, backend=MB)
        r = c.get(reverse('estado_cuentas_comedor'))
        self.assertNotEqual(r.status_code, 200)

    def test_prefill_familia_en_cargar_pago(self):
        r = self._cli().get(reverse('registrar_pago_admin_comedor'), {'familia': self.deudor.pk})
        self.assertEqual(r.status_code, 200)
        # El option de la familia queda seleccionado.
        self.assertContains(r, f'value="{self.deudor.pk}" selected')
