"""Tests de la suplantación de familias (django-hijack).

Cubre:
- La regla de permiso `solo_familias` (quién puede y a quién).
- El flujo acquire/release (entrar como familia y volver al admin).
- Que un no-admin no pueda suplantar.
- Que al VOLVER al admin se restaure su OTP (no lo manda a re-verificar 2FA).
"""

from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.contrib.auth import SESSION_KEY
from django.urls import reverse

from django_otp.plugins.otp_totp.models import TOTPDevice

from users.models import Perfil
from users.hijack_checks import solo_familias
from escuela.models import Colegio, Curso, Cliente

MB = 'django.contrib.auth.backends.ModelBackend'
# Igual que el resto de la suite: sacamos el middleware de OTP obligatorio para
# los tests de flujo puro (no queremos montar 2FA para eso).
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE
               if m != 'main.middleware.StaffOTPRequiredMiddleware']


def _familia_con_hijo(email="padre@t.com"):
    padre = Perfil.objects.create_user(
        email=email, password="x", first_name="Ana", last_name="Perez")
    col, _ = Colegio.objects.get_or_create(nombre="Mila")
    curso, _ = Curso.objects.get_or_create(curso="1A", colegio=col, nivel="PRIMARIA")
    Cliente.objects.create(usuario=padre, nombre="Beto", apellido="Perez", curso=curso)
    return padre


def _admin(email="admin@t.com"):
    return Perfil.objects.create_user(
        email=email, password="x", first_name="Super", last_name="User",
        is_superuser=True, is_staff=True)


class PermisoSoloFamiliasTest(TestCase):
    def test_admin_puede_suplantar_a_familia(self):
        self.assertTrue(solo_familias(hijacker=_admin(), hijacked=_familia_con_hijo()))

    def test_no_se_puede_suplantar_a_perfil_sin_hijos(self):
        suelto = Perfil.objects.create_user(
            email="solo@t.com", password="x", first_name="Sin", last_name="Hijos")
        self.assertFalse(solo_familias(hijacker=_admin(), hijacked=suelto))

    def test_no_se_puede_suplantar_a_otro_admin(self):
        otro_admin = _admin(email="admin2@t.com")
        self.assertFalse(solo_familias(hijacker=_admin(), hijacked=otro_admin))

    def test_no_superusuario_no_puede_suplantar(self):
        comun = _familia_con_hijo(email="comun@t.com")
        self.assertFalse(solo_familias(hijacker=comun, hijacked=_familia_con_hijo("otra@t.com")))

    def test_no_puede_suplantarse_a_si_mismo(self):
        # Un admin no es familia igual, pero cubrimos el caso pk==pk explícito.
        admin = _admin()
        self.assertFalse(solo_familias(hijacker=admin, hijacked=admin))


@override_settings(MIDDLEWARE=_MW_SIN_OTP)
class FlujoSuplantacionTest(TestCase):
    def setUp(self):
        self.padre = _familia_con_hijo()
        self.admin = _admin()

    def _login_admin(self):
        c = Client()
        c.force_login(self.admin, backend=MB)
        return c

    def test_acquire_convierte_la_sesion_en_el_padre(self):
        c = self._login_admin()
        r = c.post(reverse('hijack:acquire'), {'user_pk': self.padre.pk, 'next': '/'})
        self.assertEqual(r.status_code, 302)
        # La sesión ahora es del padre.
        self.assertEqual(int(c.session[SESSION_KEY]), self.padre.pk)
        # Y guarda el historial para poder volver.
        self.assertEqual(c.session['hijack_history'], [str(self.admin.pk)])

    def test_release_vuelve_al_admin(self):
        c = self._login_admin()
        c.post(reverse('hijack:acquire'), {'user_pk': self.padre.pk, 'next': '/'})
        r = c.post(reverse('hijack:release'), {'next': '/'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(c.session[SESSION_KEY]), self.admin.pk)
        self.assertFalse(c.session.get('hijack_history'))

    def test_no_admin_no_puede_suplantar(self):
        c = Client()
        c.force_login(self.padre, backend=MB)  # familia común
        c.post(reverse('hijack:acquire'), {'user_pk': self.padre.pk, 'next': '/'})
        # La sesión sigue siendo la del padre (no suplantó nada ni escaló).
        self.assertEqual(int(c.session[SESSION_KEY]), self.padre.pk)
        self.assertFalse(c.session.get('hijack_history'))

    def test_no_se_puede_suplantar_a_otro_admin_via_http(self):
        otro_admin = _admin(email="admin2@t.com")
        c = self._login_admin()
        c.post(reverse('hijack:acquire'), {'user_pk': otro_admin.pk, 'next': '/'})
        # No cambió de identidad: sigue siendo el admin original.
        self.assertEqual(int(c.session[SESSION_KEY]), self.admin.pk)
        self.assertFalse(c.session.get('hijack_history'))

    def test_boton_ingresar_aparece_en_lista_para_familia(self):
        # El template carga el tag {% can_hijack %} y muestra el botón para la familia.
        c = self._login_admin()
        r = c.get(reverse('lista_usuarios') + '?filtro=todos')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Ingresar a nombre de')
        self.assertContains(r, reverse('hijack:acquire'))


class RestauraOtpAlVolverTest(TestCase):
    """Con el middleware de OTP ACTIVO: al volver al admin no debe pedirle 2FA."""

    def setUp(self):
        self.padre = _familia_con_hijo()
        self.admin = _admin()
        self.device = TOTPDevice.objects.create(
            user=self.admin, name="app", confirmed=True)

    def _admin_verificado(self):
        c = Client()
        c.force_login(self.admin, backend=MB)
        # Marca la sesión como OTP-verificada (lo que hace django_otp.login).
        s = c.session
        s['otp_device_id'] = self.device.persistent_id
        s.save()
        return c

    def test_admin_verificado_navega_sin_2fa(self):
        c = self._admin_verificado()
        r = c.get('/')  # home admin
        self.assertEqual(r.status_code, 200)  # control: verificado => pasa

    def test_al_volver_de_suplantar_sigue_verificado(self):
        c = self._admin_verificado()
        c.post(reverse('hijack:acquire'), {'user_pk': self.padre.pk, 'next': '/'})
        # Mientras suplanta es el padre (no-staff): la home responde 200.
        self.assertEqual(c.get('/').status_code, 200)
        # Vuelve al admin.
        c.post(reverse('hijack:release'), {'next': '/'})
        self.assertEqual(int(c.session[SESSION_KEY]), self.admin.pk)
        # Clave: NO lo mandan a re-verificar OTP; la home admin responde 200.
        r = c.get('/')
        self.assertEqual(r.status_code, 200)
