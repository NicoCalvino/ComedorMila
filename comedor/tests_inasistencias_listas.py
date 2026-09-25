"""Los alumnos con inasistencia avisada (con o sin compensación) no aparecen en
el reporte diario, ni en sus totales, ni en la lista de asistencias."""
import json
from datetime import date, timedelta

from django.conf import settings as dj_settings
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import ValeMensual, ValeDiario, Asistencia, Inasistencia

MB = 'django.contrib.auth.backends.ModelBackend'
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']

LUNES = date(2026, 9, 28)  # un lunes cualquiera para el reporte


def fecha_asistencia():
    """Misma lógica de AsistenciaView: hoy, o el lunes si es fin de semana."""
    f = timezone.localdate()
    if f.weekday() == 5:
        f += timedelta(days=2)
    elif f.weekday() == 6:
        f += timedelta(days=1)
    return f


@override_settings(MIDDLEWARE=_MW_SIN_OTP)
class InasistenciasFueraDeListasTest(TestCase):
    def setUp(self):
        self.admin = Perfil.objects.create_user(
            email="a@t.com", password="x", first_name="S", last_name="U",
            is_superuser=True, is_staff=True)
        padre = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        col = Colegio.objects.create(nombre="M")
        cur = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        todos = dict(lunes=True, martes=True, miercoles=True, jueves=True, viernes=True)
        self.viene = Cliente.objects.create(usuario=padre, nombre="Viene", apellido="P", curso=cur)
        self.avisado = Cliente.objects.create(usuario=padre, nombre="Avisado", apellido="P", curso=cur)
        self.tardio = Cliente.objects.create(usuario=padre, nombre="Tardio", apellido="P", curso=cur)
        for cli in (self.viene, self.avisado, self.tardio):
            ValeMensual.objects.create(usuario=padre, cliente=cli, **todos)
        self.padre = padre
        self.c = Client()
        self.c.force_login(self.admin, backend=MB)

    def _avisar(self, fecha):
        Inasistencia.objects.create(cliente=self.avisado, fecha=fecha, resultado=Inasistencia.VALE_A_FAVOR)
        Inasistencia.objects.create(cliente=self.tardio, fecha=fecha, resultado=Inasistencia.SIN_COMPENSACION)

    # Reporte diario --------------------------------------------------------
    def _reporte(self, fecha):
        r = self.c.get(reverse('reporte_diario'), {'fecha': fecha.isoformat()})
        self.assertEqual(r.status_code, 200)
        return r.context

    def test_reporte_excluye_inasistencias_y_totales(self):
        self._avisar(LUNES)
        ctx = self._reporte(LUNES)
        self.assertEqual([i['cliente'] for i in ctx['lista_asistencia']], [self.viene])
        self.assertEqual(ctx['totales']['total_general'], 1)
        self.assertEqual(ctx['totales']['total_cursos'], 1)

    def test_reporte_otro_dia_no_afectado(self):
        self._avisar(LUNES)
        ctx = self._reporte(LUNES + timedelta(days=1))
        self.assertEqual(len(ctx['lista_asistencia']), 3)

    def test_reporte_excluye_vale_diario_con_inasistencia(self):
        otro = Cliente.objects.create(usuario=self.padre, nombre="Diario", apellido="P", curso=self.viene.curso)
        ValeDiario.objects.create(usuario=self.padre, cliente=otro, fecha=LUNES)
        Inasistencia.objects.create(cliente=otro, fecha=LUNES, resultado=Inasistencia.SIN_COMPENSACION)
        ctx = self._reporte(LUNES)
        self.assertNotIn(otro, [i['cliente'] for i in ctx['lista_asistencia']])

    def test_excel_reporte_excluye_inasistencias(self):
        self._avisar(LUNES)
        from comedor.views import ReporteDiarioView
        from django.test import RequestFactory
        req = RequestFactory().get('/', {'fecha': LUNES.isoformat()})
        req.user = self.admin
        vista = ReporteDiarioView(); vista.request = req; vista.kwargs = {}
        ctx = vista.get_context_data()
        self.assertEqual(len(ctx['lista_asistencia']), 1)

    # Lista de asistencias ----------------------------------------------------
    def test_asistencia_no_genera_inasistencias(self):
        f = fecha_asistencia()
        self._avisar(f)
        r = self.c.get(reverse('asistencia_dia'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([a.cliente for a in r.context['asistencias']], [self.viene])
        self.assertFalse(Asistencia.objects.filter(fecha=f, cliente=self.avisado).exists())
        self.assertFalse(Asistencia.objects.filter(fecha=f, cliente=self.tardio).exists())

    def test_asistencia_oculta_aviso_posterior_a_generar(self):
        f = fecha_asistencia()
        self.c.get(reverse('asistencia_dia'))  # la lista se genera antes del aviso
        self.assertEqual(Asistencia.objects.filter(fecha=f).count(), 3)
        self._avisar(f)
        r = self.c.get(reverse('asistencia_dia'))
        self.assertEqual([a.cliente for a in r.context['asistencias']], [self.viene])

    def test_contador_presentes_excluye_inasistencias(self):
        f = fecha_asistencia()
        a1 = Asistencia.objects.create(fecha=f, cliente=self.viene, asistio=False)
        Asistencia.objects.create(fecha=f, cliente=self.avisado, asistio=True)
        self._avisar(f)
        r = self.c.post(reverse('marcar_asistencia_ajax', args=[a1.pk]),
                        data=json.dumps({'asistio': True}), content_type='application/json')
        self.assertEqual(r.json()['total_presentes'], 1)
