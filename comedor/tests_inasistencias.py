from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import (ValeMensual, Precio, CuentaComedor, MovimientoComedor,
                            Inasistencia, ValeAFavor)
from comedor.inasistencias import puede_avisar, registrar_inasistencia, usar_vale_a_favor


def _lunes_8am():
    d = date(2026, 8, 1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return datetime.combine(d, time(8, 0))


class InasistenciaTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        self.col = Colegio.objects.create(nombre="M")
        self.cur = Curso.objects.create(curso="1A", colegio=self.col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=self.cur)
        self.lunes8 = _lunes_8am()

    def _plan(self, **dias):
        return ValeMensual.objects.create(usuario=self.u, cliente=self.cli, **dias)

    def test_puede_avisar_antes_de_9(self):
        self._plan(lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        ok, motivo = puede_avisar(self.cli, ahora=self.lunes8)
        self.assertTrue(ok, motivo)

    def test_no_avisar_despues_de_9(self):
        self._plan(lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        tarde = datetime.combine(self.lunes8.date(), time(9, 30))
        ok, _ = puede_avisar(self.cli, ahora=tarde)
        self.assertFalse(ok)

    def test_no_avisar_sin_plan(self):
        ok, _ = puede_avisar(self.cli, ahora=self.lunes8)
        self.assertFalse(ok)

    def test_no_avisar_dia_sin_comedor(self):
        # plan solo martes -> el lunes no tiene comedor
        self._plan(martes=True)
        ok, _ = puede_avisar(self.cli, ahora=self.lunes8)
        self.assertFalse(ok)

    def test_5_dias_devuelve_dinero(self):
        Precio.objects.create(colegio=self.col, alm_por_sem=5, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("188100"))
        self._plan(lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        inas = registrar_inasistencia(self.cli, ahora=self.lunes8)
        self.assertEqual(inas.resultado, Inasistencia.DEVOLUCION)
        self.assertEqual(inas.monto_devuelto, Decimal("5643.00"))  # (188100/20)*0.6
        cuenta = CuentaComedor.para(self.u)
        self.assertEqual(cuenta.saldo, Decimal("-5643.00"))  # crédito (a favor)
        self.assertTrue(cuenta.movimientos.filter(tipo=MovimientoComedor.CREDITO_INASISTENCIA).exists())

    def test_1a4_dias_genera_vale_a_favor(self):
        Precio.objects.create(colegio=self.col, alm_por_sem=2, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("90000"))
        self._plan(lunes=True, martes=True)
        inas = registrar_inasistencia(self.cli, ahora=self.lunes8)
        self.assertEqual(inas.resultado, Inasistencia.VALE_A_FAVOR)
        self.assertTrue(ValeAFavor.objects.filter(cliente=self.cli, usado=False).exists())
        self.assertEqual(CuentaComedor.para(self.u).saldo, Decimal("0.00"))  # no mueve dinero

    def test_no_avisar_dos_veces(self):
        self._plan(lunes=True, martes=True)
        Precio.objects.create(colegio=self.col, alm_por_sem=2, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("90000"))
        registrar_inasistencia(self.cli, ahora=self.lunes8)
        with self.assertRaises(ValueError):
            registrar_inasistencia(self.cli, ahora=self.lunes8)

    def test_usar_vale_a_favor_crea_vale_gratis(self):
        self._plan(lunes=True, martes=True)
        Precio.objects.create(colegio=self.col, alm_por_sem=2, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("90000"))
        Precio.objects.create(colegio=self.col, alm_por_sem=1, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("40000"))
        registrar_inasistencia(self.cli, ahora=self.lunes8)
        vaf = ValeAFavor.objects.get(cliente=self.cli, usado=False)
        # elegir un día futuro hábil
        f = timezone.localdate() + timedelta(days=7)
        while f.weekday() >= 5:
            f += timedelta(days=1)
        vale = usar_vale_a_favor(vaf, f, usuario=self.u)
        vaf.refresh_from_db()
        self.assertTrue(vaf.usado)
        self.assertEqual(vaf.vale_diario_id, vale.id)
        # gratis: no generó cargo de vale diario
        self.assertEqual(CuentaComedor.para(self.u).saldo, Decimal("0.00"))
        self.assertFalse(MovimientoComedor.objects.filter(tipo=MovimientoComedor.CARGO_VALE_DIARIO).exists())

    def test_usar_vale_a_favor_dia_pasado_falla(self):
        self._plan(lunes=True, martes=True)
        Precio.objects.create(colegio=self.col, alm_por_sem=2, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("90000"))
        registrar_inasistencia(self.cli, ahora=self.lunes8)
        vaf = ValeAFavor.objects.get(cliente=self.cli, usado=False)
        ayer = timezone.localdate() - timedelta(days=1)
        with self.assertRaises(ValueError):
            usar_vale_a_favor(vaf, ayer)
