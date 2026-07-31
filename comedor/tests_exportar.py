from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.utils import timezone
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import ValeMensual, ValeDiario, Precio

MB = 'django.contrib.auth.backends.ModelBackend'
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']
XLSX = 'spreadsheetml'


@override_settings(MIDDLEWARE=_MW_SIN_OTP)
class ExportarExcelTest(TestCase):
    def setUp(self):
        self.admin = Perfil.objects.create_user(email="a@t.com", password="x", first_name="S", last_name="U", is_superuser=True, is_staff=True)
        padre = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        col = Colegio.objects.create(nombre="M")
        cur = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        cli = Cliente.objects.create(usuario=padre, nombre="H", apellido="P", curso=cur)
        Precio.objects.create(colegio=col, alm_por_sem=2, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("90000"))
        ValeMensual.objects.create(usuario=padre, cliente=cli, martes=True, jueves=True)
        ValeDiario.objects.create(usuario=padre, cliente=cli, fecha=timezone.localdate() + timedelta(days=2))
        self.c = Client(); self.c.force_login(self.admin, backend=MB)

    def _check(self, urlname):
        r = self.c.get(reverse(urlname))
        self.assertEqual(r.status_code, 200)
        self.assertIn(XLSX, r['Content-Type'])
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertIn('.xlsx', r['Content-Disposition'])
        self.assertTrue(len(r.content) > 100)  # archivo real

    def test_facturacion(self):
        self._check('reporte_mensual_excel')

    def test_diario(self):
        self._check('reporte_diario_excel')

    def test_comedor_mensual(self):
        self._check('comedor_mensual_excel')

    def test_vales_diarios(self):
        self._check('vales_diarios_excel')

    def test_requiere_admin(self):
        padre = Perfil.objects.get(email="p@t.com")
        c = Client(); c.force_login(padre, backend=MB)
        r = c.get(reverse('reporte_mensual_excel'))
        self.assertNotEqual(r.status_code, 200)  # no admin -> no accede
