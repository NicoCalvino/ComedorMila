from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.test import TestCase, Client
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import Precio, CuentaComedor, MovimientoComedor, SolicitudPagoComedor, ValeDiario

MB = 'django.contrib.auth.backends.ModelBackend'


def _png():
    buf = BytesIO()
    Image.new('RGB', (2, 2), 'white').save(buf, 'PNG')
    return SimpleUploadedFile('comprobante.png', buf.getvalue(), content_type='image/png')


def _proximo_dia_habil():
    f = timezone.localdate() + timedelta(days=1)
    while f.weekday() >= 5:
        f += timedelta(days=1)
    return f


class PagoConValeDiarioTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        col = Colegio.objects.create(nombre="M")
        cur = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=cur)
        Precio.objects.create(colegio=col, alm_por_sem=1, nivel="PRIMARIA/SECUNDARIA", nro_de_cliente=1, precio=Decimal("40000"))
        self.c = Client(); self.c.force_login(self.u, backend=MB)

    def test_con_comprobante_crea_pago_pendiente(self):
        f = _proximo_dia_habil()
        r = self.c.post(reverse('carga_vale_diario', args=[self.cli.pk]),
                        {'fecha': f.isoformat(), 'comprobante': _png(), 'comentarios': ''})
        self.assertEqual(r.status_code, 302)
        # vale creado y cargo aplicado
        self.assertTrue(ValeDiario.objects.filter(cliente=self.cli, fecha=f).exists())
        cuenta = CuentaComedor.para(self.u)
        self.assertEqual(cuenta.saldo, Decimal("10000.00"))  # cargo del día (40000/4)
        # pago pendiente creado por el valor del día
        pago = SolicitudPagoComedor.objects.get(usuario=self.u)
        self.assertEqual(pago.estado, SolicitudPagoComedor.PENDIENTE)
        self.assertEqual(pago.monto, Decimal("10000.00"))
        self.assertTrue(pago.comprobante)  # tiene comprobante adjunto

    def test_sin_comprobante_no_crea_pago(self):
        f = _proximo_dia_habil()
        r = self.c.post(reverse('carga_vale_diario', args=[self.cli.pk]),
                        {'fecha': f.isoformat(), 'comentarios': ''})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(ValeDiario.objects.filter(cliente=self.cli, fecha=f).exists())
        self.assertEqual(CuentaComedor.para(self.u).saldo, Decimal("10000.00"))  # solo el cargo
        self.assertFalse(SolicitudPagoComedor.objects.filter(usuario=self.u).exists())  # sin pago

    def test_pago_aprobado_compensa_el_cargo(self):
        f = _proximo_dia_habil()
        self.c.post(reverse('carga_vale_diario', args=[self.cli.pk]),
                    {'fecha': f.isoformat(), 'comprobante': _png()})
        pago = SolicitudPagoComedor.objects.get(usuario=self.u)
        pago.aprobar(self.u)  # admin aprueba
        cuenta = CuentaComedor.para(self.u)
        self.assertEqual(cuenta.saldo, Decimal("0.00"))  # cargo (+10000) y pago (-10000) se compensan
