from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import ValeDiario, Precio, CuentaComedor, MovimientoComedor
from comedor.cargos import precio_vale_diario


class CargoValeDiarioTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        self.col = Colegio.objects.create(nombre="M")
        self.cur = Curso.objects.create(curso="1A", colegio=self.col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=self.cur)
        # precio 1 día/sem = 40000 -> vale diario = 10000
        Precio.objects.create(colegio=self.col, alm_por_sem=1, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("40000"))
        self.hoy = timezone.localdate()

    def _saldo(self):
        return CuentaComedor.para(self.u).saldo

    def test_precio_vale_diario(self):
        self.assertEqual(precio_vale_diario(self.cli), Decimal("10000.00"))

    def test_cobra_al_crear(self):
        vale = ValeDiario.objects.create(usuario=self.u, cliente=self.cli, fecha=self.hoy + timedelta(days=3))
        cuenta = CuentaComedor.para(self.u)
        self.assertEqual(cuenta.saldo, Decimal("10000.00"))
        self.assertTrue(cuenta.movimientos.filter(tipo=MovimientoComedor.CARGO_VALE_DIARIO, vale_diario=vale).exists())

    def test_no_cobra_dos_veces(self):
        vale = ValeDiario.objects.create(usuario=self.u, cliente=self.cli, fecha=self.hoy + timedelta(days=3))
        vale.comentarios = "editado"
        vale.save()  # segundo save, no debe volver a cobrar
        self.assertEqual(self._saldo(), Decimal("10000.00"))

    def test_acredita_al_cancelar_dia_futuro(self):
        vale = ValeDiario.objects.create(usuario=self.u, cliente=self.cli, fecha=self.hoy + timedelta(days=3))
        vale.cancelado = True
        vale.save()
        self.assertEqual(self._saldo(), Decimal("0.00"))  # cargo + crédito = 0

    def test_no_acredita_dia_pasado(self):
        vale = ValeDiario.objects.create(usuario=self.u, cliente=self.cli, fecha=self.hoy - timedelta(days=2))
        self.assertEqual(self._saldo(), Decimal("10000.00"))  # se cobró
        vale.cancelado = True
        vale.save()
        self.assertEqual(self._saldo(), Decimal("10000.00"))  # día pasado: no se devuelve

    def test_cancela_hoy_se_acredita(self):
        vale = ValeDiario.objects.create(usuario=self.u, cliente=self.cli, fecha=self.hoy)
        vale.cancelado = True
        vale.save()
        self.assertEqual(self._saldo(), Decimal("0.00"))  # hoy todavía no pasó

    def test_vale_a_favor_no_cobra(self):
        vale = ValeDiario(usuario=self.u, cliente=self.cli, fecha=self.hoy + timedelta(days=3))
        vale._skip_cargo = True
        vale.save()
        self.assertEqual(self._saldo(), Decimal("0.00"))  # gratis, no cobra


class RedirectComedorTest(TestCase):
    def setUp(self):
        self.padre = Perfil.objects.create_user(email="pa@t.com", password="x", first_name="A", last_name="P")
        self.admin = Perfil.objects.create_user(email="ad@t.com", password="x", first_name="S", last_name="U", is_superuser=True, is_staff=True)

    def _success_url(self, user):
        from types import SimpleNamespace
        from comedor.views import CargarValeDiarioView
        v = CargarValeDiarioView()
        v.request = SimpleNamespace(user=user)
        return str(v.get_success_url())

    def test_padre_vuelve_a_comedor_familia(self):
        from django.urls import reverse
        self.assertEqual(self._success_url(self.padre), reverse('comedor_familia'))

    def test_admin_vuelve_a_comedor_home(self):
        from django.urls import reverse
        self.assertEqual(self._success_url(self.admin), reverse('comedor_home'))
