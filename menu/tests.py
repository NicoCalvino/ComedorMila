from django.test import TestCase, Client, override_settings
from django.conf import settings as dj_settings
from django.urls import reverse
from users.models import Perfil
from escuela.models import Colegio, Curso, Cliente
from menu.models import MenuJardin

MB = 'django.contrib.auth.backends.ModelBackend'
# El staff (admin) queda obligado a verificar OTP por StaffOTPRequiredMiddleware.
# Para probar las vistas de admin lo quitamos, igual que en los tests de comedor.
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']


class MenuJardinModelTest(TestCase):
    def test_orden_se_asigna_en_save(self):
        m = MenuJardin.objects.create(dia="MIERCOLES", plato_principal="Pollo")
        self.assertEqual(m.orden, 2)
        v = MenuJardin.objects.create(dia="VIERNES")
        self.assertEqual(v.orden, 4)
        # El ordering por 'orden' debe devolver los días en orden Lun->Vie.
        MenuJardin.objects.create(dia="LUNES")
        dias = list(MenuJardin.objects.values_list("dia", flat=True))
        self.assertEqual(dias, ["LUNES", "MIERCOLES", "VIERNES"])

    def test_dia_unico(self):
        MenuJardin.objects.create(dia="LUNES", plato_principal="A")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            MenuJardin.objects.create(dia="LUNES", plato_principal="B")


@override_settings(MIDDLEWARE=_MW_SIN_OTP)
class MenuJardinAdminViewTest(TestCase):
    def setUp(self):
        self.admin = Perfil.objects.create_superuser(
            email="admin@t.com", password="x", first_name="Ad", last_name="Min")
        self.padre = Perfil.objects.create_user(
            email="padre@t.com", password="x", first_name="Pa", last_name="Dre")
        self.c = Client()

    def test_superuser_accede_y_ve_dias(self):
        self.c.force_login(self.admin, backend=MB)
        r = self.c.get(reverse("menu_jardin"))
        self.assertEqual(r.status_code, 200)
        for d in ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]:
            self.assertContains(r, d)
        # Se crearon las 5 filas fijas.
        self.assertEqual(MenuJardin.objects.count(), 5)

    def test_boton_menu_jardin_en_home(self):
        self.c.force_login(self.admin, backend=MB)
        r = self.c.get(reverse("home_menu"))
        self.assertContains(r, reverse("menu_jardin"))
        self.assertContains(r, "Menú Jardín")

    def test_padre_no_puede_acceder(self):
        self.c.force_login(self.padre, backend=MB)
        r = self.c.get(reverse("menu_jardin"))
        self.assertEqual(r.status_code, 302)  # redirigido a home
        self.assertEqual(MenuJardin.objects.count(), 0)

    def test_post_guarda_los_cinco_dias(self):
        self.c.force_login(self.admin, backend=MB)
        data = {}
        for d in ["LUNES", "MARTES", "MIERCOLES", "JUEVES", "VIERNES"]:
            data[f"principal_{d}"] = f"Principal {d}"
            data[f"postre_{d}"] = f"Postre {d}"
        r = self.c.post(reverse("menu_jardin"), data)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(MenuJardin.objects.count(), 5)
        lun = MenuJardin.objects.get(dia="LUNES")
        self.assertEqual(lun.plato_principal, "Principal LUNES")
        self.assertEqual(lun.postre, "Postre LUNES")


class MenuJardinUsuarioTest(TestCase):
    def setUp(self):
        self.col = Colegio.objects.create(nombre="Mila")
        self.curso_jardin = Curso.objects.create(curso="Sala5", colegio=self.col, nivel="JARDIN")
        self.curso_prim = Curso.objects.create(curso="1A", colegio=self.col, nivel="PRIMARIA")
        # Cargamos un menú de jardín.
        MenuJardin.objects.create(dia="LUNES", plato_principal="Fideos con tuco", postre="Fruta")
        MenuJardin.objects.create(dia="MARTES", plato_principal="Milanesa", postre="Gelatina")
        self.c = Client()

    def _padre_con(self, nivel):
        u = Perfil.objects.create_user(
            email=f"{nivel}@t.com", password="x", first_name="P", last_name="A")
        curso = self.curso_jardin if nivel == "JARDIN" else self.curso_prim
        Cliente.objects.create(usuario=u, nombre="H", apellido="A", curso=curso)
        return u

    def test_padre_con_hijo_jardin_ve_bloque(self):
        u = self._padre_con("JARDIN")
        self.c.force_login(u, backend=MB)
        r = self.c.get(reverse("calendar_view"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["tiene_jardin"])
        self.assertIsNotNone(r.context["menu_jardin"])
        self.assertContains(r, "Menú Jardín")
        self.assertContains(r, "Fideos con tuco")
        self.assertContains(r, "Milanesa")

    def test_padre_sin_hijo_jardin_no_ve_bloque(self):
        u = self._padre_con("PRIMARIA")
        self.c.force_login(u, backend=MB)
        r = self.c.get(reverse("calendar_view"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.context["tiene_jardin"])
        self.assertIsNone(r.context["menu_jardin"])
        self.assertNotContains(r, "Fideos con tuco")

    def test_bloque_no_aparece_si_no_hay_menu_cargado(self):
        MenuJardin.objects.all().delete()  # sin menú configurado
        u = self._padre_con("JARDIN")
        self.c.force_login(u, backend=MB)
        r = self.c.get(reverse("calendar_view"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["tiene_jardin"])
        self.assertIsNone(r.context["menu_jardin"])
