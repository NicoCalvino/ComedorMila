from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.test import TestCase
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import (ValeMensual, Precio, CuentaComedor, MovimientoComedor,
                            Inasistencia, ValeAFavor)
from comedor.inasistencias import (registrar_inasistencia_dia, registrar_inasistencias,
                                   usar_vale_a_favor, tiene_plan, dias_plan_legibles)


def _lunes(y, m):
    d = date(y, m, 1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


class InasistenciaTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        self.col = Colegio.objects.create(nombre="M")
        self.cur = Curso.objects.create(curso="1A", colegio=self.col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=self.cur)
        self.l1 = _lunes(2026, 8)
        self.ahora8 = datetime.combine(self.l1, time(8, 0))       # hoy = lunes 08:00
        self.ahora930 = datetime.combine(self.l1, time(9, 30))    # hoy = lunes 09:30
        self.l2 = self.l1 + timedelta(days=7)                     # lunes futuro
        self.mar2 = self.l2 + timedelta(days=1)                   # martes futuro

    def _plan(self, **dias):
        return ValeMensual.objects.create(usuario=self.u, cliente=self.cli, **dias)

    def _saldo(self):
        return CuentaComedor.para(self.u).saldo

    def test_dia_futuro_5dias_credita(self):
        Precio.objects.create(colegio=self.col, alm_por_sem=5, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("188100"))
        self._plan(lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        r = registrar_inasistencia_dia(self.cli, self.l2, ahora=self.ahora8)
        self.assertEqual(r['resultado'], Inasistencia.DEVOLUCION)
        self.assertEqual(r['monto'], Decimal("5643.00"))
        self.assertEqual(self._saldo(), Decimal("-5643.00"))

    def test_dia_futuro_1a4_vale(self):
        self._plan(lunes=True, martes=True)
        r = registrar_inasistencia_dia(self.cli, self.l2, ahora=self.ahora8)
        self.assertEqual(r['resultado'], Inasistencia.VALE_A_FAVOR)
        self.assertTrue(ValeAFavor.objects.filter(cliente=self.cli, usado=False).exists())
        self.assertEqual(self._saldo(), Decimal("0.00"))

    def test_hoy_antes_de_9_compensa(self):
        self._plan(lunes=True)
        r = registrar_inasistencia_dia(self.cli, self.l1, ahora=self.ahora8)
        self.assertEqual(r['resultado'], Inasistencia.VALE_A_FAVOR)

    def test_hoy_despues_de_9_sin_compensacion(self):
        self._plan(lunes=True)
        r = registrar_inasistencia_dia(self.cli, self.l1, ahora=self.ahora930)
        self.assertEqual(r['resultado'], Inasistencia.SIN_COMPENSACION)
        self.assertTrue(Inasistencia.objects.filter(cliente=self.cli, fecha=self.l1).exists())  # queda constancia
        self.assertFalse(ValeAFavor.objects.filter(cliente=self.cli).exists())
        self.assertEqual(self._saldo(), Decimal("0.00"))

    def test_dia_pasado_error(self):
        self._plan(lunes=True)
        with self.assertRaises(ValueError):
            registrar_inasistencia_dia(self.cli, self.l1 - timedelta(days=7), ahora=self.ahora8)

    def test_no_es_dia_de_plan_error(self):
        self._plan(lunes=True)  # solo lunes -> el martes no es día de comedor
        with self.assertRaises(ValueError):
            registrar_inasistencia_dia(self.cli, self.mar2, ahora=self.ahora8)

    def test_no_avisar_dos_veces(self):
        self._plan(lunes=True)
        registrar_inasistencia_dia(self.cli, self.l2, ahora=self.ahora8)
        with self.assertRaises(ValueError):
            registrar_inasistencia_dia(self.cli, self.l2, ahora=self.ahora8)

    def test_batch_varios_dias(self):
        self._plan(lunes=True)  # solo lunes
        res = registrar_inasistencias(self.cli, [self.l1, self.l2, self.mar2], ahora=self.ahora8)
        self.assertEqual(len(res['ok']), 2)         # l1 (hoy 8am) y l2 (futuro) -> ok
        self.assertEqual(len(res['errores']), 1)    # mar2 no es día de plan
        self.assertEqual(res['errores'][0][0], self.mar2)

    def test_dias_plan_legibles(self):
        self._plan(lunes=True, miercoles=True, viernes=True)
        self.assertEqual(dias_plan_legibles(self.cli), ["Lunes", "Miércoles", "Viernes"])
        self.assertTrue(tiene_plan(self.cli))

    def test_usar_vale_a_favor_crea_vale_gratis(self):
        self._plan(lunes=True)
        registrar_inasistencia_dia(self.cli, self.l2, ahora=self.ahora8)
        vaf = ValeAFavor.objects.get(cliente=self.cli, usado=False)
        from django.utils import timezone
        f = timezone.localdate() + timedelta(days=7)
        while f.weekday() >= 5:
            f += timedelta(days=1)
        vale = usar_vale_a_favor(vaf, f, usuario=self.u)
        vaf.refresh_from_db()
        self.assertTrue(vaf.usado)
        self.assertEqual(self._saldo(), Decimal("0.00"))
        self.assertFalse(MovimientoComedor.objects.filter(tipo=MovimientoComedor.CARGO_VALE_DIARIO).exists())


class InasistenciaVistaTest(TestCase):
    def setUp(self):
        from escuela.models import Colegio, Curso, Cliente
        self.u = Perfil.objects.create_user(email="pv@t.com", password="x", first_name="A", last_name="P")
        self.col = Colegio.objects.create(nombre="M")
        self.cur = Curso.objects.create(curso="1A", colegio=self.col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=self.cur)

    def test_vista_batch_crea_varias(self):
        from django.test import Client
        from django.urls import reverse
        from django.utils import timezone
        Precio.objects.create(colegio=self.col, alm_por_sem=5, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("100000"))
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        dias, d = [], timezone.localdate() + timedelta(days=1)
        while len(dias) < 2:
            if d.weekday() < 5:
                dias.append(d)
            d += timedelta(days=1)
        c = Client(); c.force_login(self.u, backend='django.contrib.auth.backends.ModelBackend')
        r = c.post(reverse('avisar_inasistencias', args=[self.cli.pk]), {'fechas': [x.isoformat() for x in dias]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Inasistencia.objects.filter(cliente=self.cli).count(), 2)

    def test_vista_get_ok(self):
        from django.test import Client
        from django.urls import reverse
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True)
        c = Client(); c.force_login(self.u, backend='django.contrib.auth.backends.ModelBackend')
        r = c.get(reverse('avisar_inasistencias', args=[self.cli.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Avisar inasistencias")
        self.assertContains(r, "Lunes")
