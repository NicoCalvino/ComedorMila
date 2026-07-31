from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import CuentaComedor, MovimientoComedor

MB = 'django.contrib.auth.backends.ModelBackend'


class ComedorFamiliaUITest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        col = Colegio.objects.create(nombre="M")
        cur = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=cur)
        self.cuenta = CuentaComedor.para(self.u)
        self.cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("100000"), concepto="Cargo mensual 2026-08", periodo="2026-08")
        self.cuenta.agregar_movimiento(MovimientoComedor.PAGO, Decimal("-30000"), concepto="Pago de comedor")
        self.c = Client(); self.c.force_login(self.u, backend=MB)

    def test_muestra_saldo_real_deuda(self):
        r = self.c.get(reverse('comedor_familia'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Debés")
        self.assertContains(r, "70.000")           # 100000 - 30000
        self.assertContains(r, "Ver todo")
        self.assertContains(r, "Cargo mensual 2026-08")

    def test_historial_completo(self):
        r = self.c.get(reverse('historial_comedor'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cargo mensual 2026-08")
        self.assertContains(r, "Pago de comedor")

    def test_historial_aislado_por_familia(self):
        otro = Perfil.objects.create_user(email="o@t.com", password="x", first_name="B", last_name="Q")
        cta2 = CuentaComedor.para(otro)
        cta2.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("55555"), concepto="Cargo de OTRA familia", periodo="2026-08")
        r = self.c.get(reverse('historial_comedor'))
        self.assertNotContains(r, "Cargo de OTRA familia")

    def test_saldo_a_favor(self):
        # otro pago que deja saldo negativo (a favor)
        self.cuenta.agregar_movimiento(MovimientoComedor.PAGO, Decimal("-90000"), concepto="Pago extra")
        r = self.c.get(reverse('comedor_familia'))
        self.assertContains(r, "A favor")           # 70000 - 90000 = -20000
        self.assertContains(r, "20.000")
