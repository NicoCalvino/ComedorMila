from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError, transaction
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import (
    CuentaComedor, MovimientoComedor, ConfiguracionComedor,
)


class CuentaComedorTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")

    def test_saldo_suma_movimientos_firmados(self):
        cuenta = CuentaComedor.para(self.u)
        self.assertEqual(cuenta.saldo, Decimal("0.00"))
        cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("230000"), periodo="2026-08")
        cuenta.agregar_movimiento(MovimientoComedor.PAGO, Decimal("-100000"))
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.saldo, Decimal("130000.00"))  # 230000 - 100000
        # recalcular desde cero da lo mismo
        self.assertEqual(cuenta.recalcular_saldo(), Decimal("130000.00"))

    def test_credito_deja_saldo_a_favor(self):
        cuenta = CuentaComedor.para(self.u)
        cuenta.agregar_movimiento(MovimientoComedor.PAGO, Decimal("-5000"))
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.saldo, Decimal("-5000.00"))  # negativo = a favor

    def test_un_solo_cargo_mensual_por_periodo(self):
        cuenta = CuentaComedor.para(self.u)
        cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("1000"), periodo="2026-08")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MovimientoComedor.objects.create(
                    cuenta=cuenta, tipo=MovimientoComedor.CARGO_MENSUAL,
                    monto=Decimal("1000"), periodo="2026-08",
                )

    def test_dos_periodos_distintos_ok(self):
        cuenta = CuentaComedor.para(self.u)
        cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("1000"), periodo="2026-08")
        cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("1000"), periodo="2026-09")
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.saldo, Decimal("2000.00"))

    def test_config_singleton(self):
        c1 = ConfiguracionComedor.get_solo()
        self.assertEqual(c1.pk, 1)
        self.assertEqual(c1.porcentaje_devolucion_inasistencia, Decimal("0.60"))
        self.assertEqual(c1.divisor_valor_dia, 20)
        c1.divisor_valor_dia = 22
        c1.save()
        self.assertEqual(ConfiguracionComedor.objects.count(), 1)  # sigue habiendo una sola
        self.assertEqual(ConfiguracionComedor.get_solo().divisor_valor_dia, 22)

    def test_no_toca_kiosco(self):
        # crear cliente => se autogenera una tarjeta con saldo 0 (kiosco)
        col = Colegio.objects.create(nombre="M")
        cur = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=cur)
        tarjeta = cli.tarjeta_set.first()
        saldo_kiosco_antes = tarjeta.saldo
        cuenta = CuentaComedor.para(self.u)
        cuenta.agregar_movimiento(MovimientoComedor.CARGO_MENSUAL, Decimal("50000"), periodo="2026-08")
        tarjeta.refresh_from_db()
        self.assertEqual(tarjeta.saldo, saldo_kiosco_antes)  # el saldo del kiosco NO cambió
