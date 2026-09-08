from datetime import date
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import ValeMensual, Precio, CuentaComedor, MovimientoComedor
from comedor.cargos import (
    generar_cargos_mensuales, cargo_mensual_padre, desvios_del_periodo,
    regularizar_familia,
)

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

    def test_cargo_queda_imputado_al_hijo(self):
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        generar_cargos_mensuales(2026, 8)
        mov = CuentaComedor.para(self.u).movimientos.get(tipo=MovimientoComedor.CARGO_MENSUAL, periodo="2026-08")
        self.assertEqual(mov.cliente, self.cli)
        self.assertIn(self.cli.nombre, mov.concepto)


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


class AltaDeHermanoMitadDeMesTest(TestCase):
    """El bug real: se genera el mes, después se anota otro hijo de la misma
    familia y volver a generar el mes tiene que cobrarle SOLO a ese hijo."""

    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        self.col = Colegio.objects.create(nombre="M")
        self.cur = Curso.objects.create(curso="1A", colegio=self.col, nivel="PRIMARIA")
        self.h1 = Cliente.objects.create(usuario=self.u, nombre="Uno", apellido="P", curso=self.cur)
        self.h2 = Cliente.objects.create(usuario=self.u, nombre="Dos", apellido="P", curso=self.cur)
        Precio.objects.create(colegio=self.col, alm_por_sem=2, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("98000"))
        Precio.objects.create(colegio=self.col, alm_por_sem=2, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=2, precio=Decimal("88000"))
        ValeMensual.objects.create(usuario=self.u, cliente=self.h1, miercoles=True, jueves=True)

    def _cuenta(self):
        return CuentaComedor.para(self.u)

    def test_regenerar_cobra_solo_al_hermano_nuevo(self):
        generar_cargos_mensuales(2026, 9)
        self.assertEqual(self._cuenta().saldo, Decimal("98000.00"))

        # El segundo hijo se anota después de generado el mes.
        ValeMensual.objects.create(usuario=self.u, cliente=self.h2, jueves=True, viernes=True,
                                   vigente_desde=date(2026, 9, 8))
        res = generar_cargos_mensuales(2026, 9)

        self.assertEqual(len(res['creados']), 1)
        self.assertEqual(res['creados'][0]['cliente'], self.h2)
        self.assertEqual(res['creados'][0]['monto'], Decimal("88000.00"))
        # 98.000 del primero (intacto) + 88.000 del hermano nuevo.
        self.assertEqual(self._cuenta().saldo, Decimal("186000.00"))
        self.assertEqual(self._cuenta().movimientos.filter(
            tipo=MovimientoComedor.CARGO_MENSUAL, periodo="2026-09").count(), 2)

    def test_no_duplica_al_hijo_ya_cobrado(self):
        generar_cargos_mensuales(2026, 9)
        ValeMensual.objects.create(usuario=self.u, cliente=self.h2, jueves=True, viernes=True)
        generar_cargos_mensuales(2026, 9)
        generar_cargos_mensuales(2026, 9)
        self.assertEqual(self._cuenta().saldo, Decimal("186000.00"))
        self.assertEqual(self._cuenta().movimientos.filter(
            tipo=MovimientoComedor.CARGO_MENSUAL, periodo="2026-09", cliente=self.h1).count(), 1)

    def test_cargo_viejo_sin_detalle_se_atribuye_por_importe(self):
        # Simula lo que quedó en la base antes de este cambio: un único cargo
        # familiar, sin hijo imputado.
        self._cuenta().agregar_movimiento(
            MovimientoComedor.CARGO_MENSUAL, Decimal("98000"),
            concepto="Cargo mensual 2026-09", periodo="2026-09",
        )
        ValeMensual.objects.create(usuario=self.u, cliente=self.h2, jueves=True, viernes=True)

        res = generar_cargos_mensuales(2026, 9)
        self.assertEqual(len(res['creados']), 1)
        self.assertEqual(res['creados'][0]['cliente'], self.h2)
        self.assertEqual(self._cuenta().saldo, Decimal("186000.00"))

    def test_desvio_y_regularizacion(self):
        self._cuenta().agregar_movimiento(
            MovimientoComedor.CARGO_MENSUAL, Decimal("98000"),
            concepto="Cargo mensual 2026-09", periodo="2026-09",
        )
        # Cambia el plan del hijo ya cobrado: ahora corresponde otro importe.
        ValeMensual.objects.create(usuario=self.u, cliente=self.h2, jueves=True, viernes=True)

        control = desvios_del_periodo(2026, 9)
        self.assertEqual(len(control['desvios']), 1)
        self.assertEqual(control['desvios'][0]['diferencia'], Decimal("88000.00"))

        regularizar_familia(self.u, 2026, 9)
        self.assertEqual(self._cuenta().saldo, Decimal("186000.00"))
        # Ya regularizada: no vuelve a aparecer en el control.
        self.assertEqual(len(desvios_del_periodo(2026, 9)['desvios']), 0)

    def test_regulariza_cambio_de_plan_con_ajuste(self):
        generar_cargos_mensuales(2026, 9)  # 98.000 imputado al hijo 1
        # El hijo pasa de 2 a 3 días a mitad de mes.
        Precio.objects.create(colegio=self.col, alm_por_sem=3, nivel="PRIMARIA/SECUNDARIA",
                              nro_de_cliente=1, precio=Decimal("146500"))
        vale = ValeMensual.objects.get(cliente=self.h1)
        vale.viernes = True
        vale.save()

        control = desvios_del_periodo(2026, 9)
        self.assertEqual(control['desvios'][0]['diferencia'], Decimal("48500.00"))

        resultado = regularizar_familia(self.u, 2026, 9)
        self.assertIsNotNone(resultado['ajuste'])
        self.assertEqual(self._cuenta().saldo, Decimal("146500.00"))
        # No se re-cobró el cargo del hijo: sigue habiendo uno solo.
        self.assertEqual(self._cuenta().movimientos.filter(
            tipo=MovimientoComedor.CARGO_MENSUAL, periodo="2026-09").count(), 1)
