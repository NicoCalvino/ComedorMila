from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from comedor.models import ValeMensual, Precio
from comedor.cargos import generar_cargos_mensuales

MB = 'django.contrib.auth.backends.ModelBackend'
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']


class DesactivarUsuarioTest(TestCase):
    def setUp(self):
        self.admin = Perfil.objects.create_user(
            email="a@t.com", password="x", first_name="S", last_name="U",
            is_superuser=True, is_staff=True,
        )
        self.u = Perfil.objects.create_user(email="p@t.com", password="x", first_name="A", last_name="P")
        col = Colegio.objects.create(nombre="M")
        cur = Curso.objects.create(curso="1A", colegio=col, nivel="PRIMARIA")
        self.cli = Cliente.objects.create(usuario=self.u, nombre="H", apellido="P", curso=cur)
        Precio.objects.create(colegio=col, alm_por_sem=5, nivel="PRIMARIA/SECUNDARIA",
                              nro_de_cliente=1, precio=Decimal("200000"))
        ValeMensual.objects.create(usuario=self.u, cliente=self.cli, lunes=True, martes=True,
                                   miercoles=True, jueves=True, viernes=True)

    def test_usuario_desactivado_no_genera_cargos(self):
        self.u.is_active = False
        self.u.save()
        res = generar_cargos_mensuales(2026, 8)
        self.assertEqual(res['creados'], [])

    def test_usuario_activo_si_genera_cargos(self):
        res = generar_cargos_mensuales(2026, 8)
        self.assertEqual(len(res['creados']), 1)

    @override_settings(MIDDLEWARE=_MW_SIN_OTP)
    def test_admin_desactiva_y_reactiva(self):
        c = Client(); c.force_login(self.admin, backend=MB)
        url = reverse('cambiar_estado_usuario', args=[self.u.pk])
        c.post(url)
        self.u.refresh_from_db()
        self.assertFalse(self.u.is_active)
        c.post(url)
        self.u.refresh_from_db()
        self.assertTrue(self.u.is_active)

    @override_settings(MIDDLEWARE=_MW_SIN_OTP)
    def test_no_se_puede_desactivar_superusuario(self):
        otro_admin = Perfil.objects.create_user(
            email="b@t.com", password="x", first_name="O", last_name="A",
            is_superuser=True, is_staff=True,
        )
        c = Client(); c.force_login(self.admin, backend=MB)
        c.post(reverse('cambiar_estado_usuario', args=[otro_admin.pk]))
        otro_admin.refresh_from_db()
        self.assertTrue(otro_admin.is_active)

    def test_usuario_normal_no_puede_desactivar(self):
        otro = Perfil.objects.create_user(email="c@t.com", password="x", first_name="C", last_name="C")
        c = Client(); c.force_login(otro, backend=MB)
        c.post(reverse('cambiar_estado_usuario', args=[self.u.pk]))
        self.u.refresh_from_db()
        self.assertTrue(self.u.is_active)

    def test_desactivado_no_puede_ingresar(self):
        self.u.is_active = False
        self.u.save()
        from django.contrib.auth.backends import ModelBackend
        self.assertIsNone(ModelBackend().authenticate(None, email="p@t.com", password="x"))
