"""Los comprobantes del comedor aceptan imagen o PDF (antes solo imagen)."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.forms import SolicitudPagoComedorForm
from comedor.models import Precio, SolicitudPagoComedor, ValeDiario
from comedor.validators import validar_comprobante

MB = 'django.contrib.auth.backends.ModelBackend'

PDF_MINIMO = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
)


def _pdf(nombre="comprobante.pdf", contenido=PDF_MINIMO):
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


def _png(nombre="c.png"):
    buf = BytesIO()
    Image.new('RGB', (2, 2), 'white').save(buf, 'PNG')
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type='image/png')


class ValidadorComprobanteTest(TestCase):
    def test_acepta_pdf(self):
        validar_comprobante(_pdf())

    def test_acepta_png(self):
        validar_comprobante(_png())

    def test_rechaza_pdf_falso(self):
        with self.assertRaises(ValidationError):
            validar_comprobante(_pdf(contenido=b"esto no es un pdf"))

    def test_rechaza_imagen_falsa(self):
        with self.assertRaises(ValidationError):
            validar_comprobante(SimpleUploadedFile("foto.jpg", b"no soy una imagen", content_type="image/jpeg"))

    def test_rechaza_otra_extension(self):
        with self.assertRaises(ValidationError):
            validar_comprobante(SimpleUploadedFile("datos.txt", b"hola", content_type="text/plain"))

    def test_deja_el_archivo_al_principio(self):
        f = _pdf()
        validar_comprobante(f)
        self.assertEqual(f.read(5), b"%PDF-")


class PagoComedorConPdfTest(TestCase):
    def setUp(self):
        self.u = Perfil.objects.create_user(email="pdf@t.com", password="x", first_name="A", last_name="P")

    def test_form_acepta_pdf(self):
        f = SolicitudPagoComedorForm(data={'monto': '30000'}, files={'comprobante': _pdf()})
        self.assertTrue(f.is_valid(), f.errors)

    def test_form_rechaza_txt(self):
        f = SolicitudPagoComedorForm(
            data={'monto': '30000'},
            files={'comprobante': SimpleUploadedFile("a.txt", b"hola", content_type="text/plain")},
        )
        self.assertFalse(f.is_valid())
        self.assertIn('comprobante', f.errors)

    def test_padre_envia_pago_con_pdf(self):
        c = Client(); c.force_login(self.u, backend=MB)
        r = c.post(reverse('registrar_pago_comedor'), {'monto': '30000', 'comprobante': _pdf()})
        self.assertRedirects(r, reverse('comedor_familia'), fetch_redirect_response=False)
        sol = SolicitudPagoComedor.objects.get(usuario=self.u)
        self.assertTrue(sol.comprobante.name.endswith(".pdf"))
        self.assertEqual(sol.estado, SolicitudPagoComedor.PENDIENTE)

    def test_vale_diario_con_pdf_crea_pago_pendiente(self):
        col = Colegio.objects.create(nombre="M")
        cur = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=cur)
        Precio.objects.create(colegio=col, alm_por_sem=1, nivel="PRIMARIA/SECUNDARIA",
                              nro_de_cliente=1, precio=Decimal("40000"))
        fecha = timezone.localdate() + timedelta(days=1)
        while fecha.weekday() >= 5:
            fecha += timedelta(days=1)
        c = Client(); c.force_login(self.u, backend=MB)
        r = c.post(reverse('carga_vale_diario', args=[cli.pk]),
                   {'fecha': fecha.isoformat(), 'comprobante': _pdf(), 'comentarios': ''})
        self.assertEqual(r.status_code, 302)
        vale = ValeDiario.objects.get(cliente=cli, fecha=fecha)
        self.assertTrue(vale.comprobante.name.endswith(".pdf"))
        pago = SolicitudPagoComedor.objects.get(usuario=self.u)
        self.assertTrue(pago.comprobante.name.endswith(".pdf"))
