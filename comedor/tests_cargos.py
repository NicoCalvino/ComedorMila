import calendar
from datetime import date
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import ValeMensual, Precio, CuentaComedor, MovimientoComedor
from comedor.cargos import generar_cargos_mensuales, cargo_mensual_padre, factor_prorrateo

MB = 'django.contrib.auth.backends.ModelBackend'
# Middleware sin el gate de OTP para staff (en tests no configuramos OTP).
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']


def _mondays(year, month):
    return [d for d in calendar.Calendar().itermonthdates(year, month)
            if d.month == month and d.weekday() == 0]


class CargosMensualesTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        self.col = Colegio.objects.create(nombre="M")
        self.cur = Curso.objects.create(curso="1A", colegio=self.col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=self.cur)
        Precio.objects.create(colegio=self.col, alm_por_sem=5, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("200000"))
        Precio.objects.create(colegio=self.col, alm_por_sem=1, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("50000"))

    def test_mes_completo_sin_vigencia(self):
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli,
                                   lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        res = generar_cargos_mensuales(2026, 8)
        self.assertEqual(len(res['creados']), 1)
        self.assertEqual(res['total'], Decimal("200000.00"))
        cuenta = CuentaComedor.objects.get(usuario=self.u)
        self.assertEqual(cuenta.saldo, Decimal("200000.00"))
        mov = cuenta.movimientos.get(tipo=MovimientoComedor.CARGO_MENSUAL, periodo="2026-08")
        self.assertEqual(mov.monto, Decimal("200000.00"))

    def test_idempotente(self):
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        generar_cargos_mensuales(2026, 8)
        res2 = generar_cargos_mensuales(2026, 8)
        self.assertEqual(len(res2['creados']), 0)
        self.assertEqual(res2['omitidos'][0]['motivo'], 'ya_generado')
        cuenta = CuentaComedor.objects.get(usuario=self.u)
        self.assertEqual(cuenta.movimientos.filter(tipo=MovimientoComedor.CARGO_MENSUAL, periodo="2026-08").count(), 1)

    def test_prorrateo_mitad_de_mes(self):
        mondays = _mondays(2026, 8)
        n = len(mondays)
        vale = ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True)
        vale.vigente_desde = mondays[1]   # desde el 2do lunes -> pierde 1 de n
        vale.save()
        factor = factor_prorrateo(vale, 2026, 8)
        self.assertEqual(factor, Decimal(n - 1) / Decimal(n))
        total, detalle = cargo_mensual_padre(self.u, 2026, 8)
        esperado = (Decimal("50000") * (Decimal(n - 1) / Decimal(n))).quantize(Decimal("0.01"))
        self.assertEqual(total, esperado)
        self.assertLess(total, Decimal("50000"))

    def test_factor_bordes(self):
        vale = ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True, vigente_desde=date(2026, 8, 1))
        self.assertEqual(factor_prorrateo(vale, 2026, 8), Decimal("1"))
        vale.vigente_desde = date(2026, 7, 1)
        self.assertEqual(factor_prorrateo(vale, 2026, 8), Decimal("1"))
        vale.vigente_desde = date(2026, 9, 1)
        self.assertEqual(factor_prorrateo(vale, 2026, 8), Decimal("0"))

    @override_settings(MIDDLEWARE=_MW_SIN_OTP)
    def test_vista_admin_genera(self):
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        admin = Perfil.objects.create_user(email="a@t.com", password="x", first_name="S", last_name="U", is_superuser=True, is_staff=True)
        c = Client(); c.force_login(admin, backend=MB)
        r = c.post(reverse('generar_cargos_mensuales'), {'year': 2026, 'month': 8})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Resultado")
        self.assertTrue(CuentaComedor.objects.get(usuario=self.u).movimientos.filter(periodo="2026-08").exists())
