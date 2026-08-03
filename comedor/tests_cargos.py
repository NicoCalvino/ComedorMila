from datetime import date
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import ValeMensual, Precio, CuentaComedor, MovimientoComedor
from comedor.cargos import generar_cargos_mensuales, cargo_mensual_padre

MB = 'django.contrib.auth.backends.ModelBackend'
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']


class CargosMensualesTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        self.col = Colegio.objects.create(nombre="M")
        self.cur = Curso.objects.create(curso="1A", colegio=self.col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=self.cur)
        Precio.objects.create(colegio=self.col, alm_por_sem=5, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("200000"))

    def test_mes_completo(self):
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli,
                                   lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        res = generar_cargos_mensuales(2026, 8)
        self.assertEqual(len(res['creados']), 1)
        self.assertEqual(res['total'], Decimal("200000.00"))
        self.assertEqual(CuentaComedor.objects.get(usuario=self.u).saldo, Decimal("200000.00"))

    def test_nunca_prorratea_aunque_alta_mitad_de_mes(self):
        # vigente_desde a mitad de mes NO reduce el cargo: siempre mes completo.
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli,
                                   lunes=True, martes=True, miercoles=True, jueves=True, viernes=True,
                                   vigente_desde=date(2026, 8, 20))
        total, _ = cargo_mensual_padre(self.u, 2026, 8)
        self.assertEqual(total, Decimal("200000.00"))

    def test_idempotente(self):
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        generar_cargos_mensuales(2026, 8)
        res2 = generar_cargos_mensuales(2026, 8)
        self.assertEqual(len(res2['creados']), 0)
        self.assertEqual(res2['omitidos'][0]['motivo'], 'ya_generado')
        self.assertEqual(CuentaComedor.para(self.u).movimientos.filter(tipo=MovimientoComedor.CARGO_MENSUAL, periodo="2026-08").count(), 1)

    def test_admin_edita_monto_recalcula_saldo(self):
        cuenta = CuentaComedor.para(self.u)
        mov = cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("200000"), periodo="2026-08")
        # el gerente ajusta el cargo (ej. alta a mitad de mes) editando el movimiento
        mov.monto = Decimal("120000")
        mov.save()
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.saldo, Decimal("120000.00"))

    def test_admin_borra_movimiento_recalcula_saldo(self):
        cuenta = CuentaComedor.para(self.u)
        mov = cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("200000"), periodo="2026-08")
        mov.delete()
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.saldo, Decimal("0.00"))

    @override_settings(MIDDLEWARE=_MW_SIN_OTP)
    def test_vista_admin_genera(self):
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        admin = Perfil.objects.create_user(email="a@t.com", password="x", first_name="S", last_name="U", is_superuser=True, is_staff=True)
        c = Client(); c.force_login(admin, backend=MB)
        r = c.post(reverse('generar_cargos_mensuales'), {'year': 2026, 'month': 8})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(CuentaComedor.objects.get(usuario=self.u).movimientos.filter(periodo="2026-08").exists())
