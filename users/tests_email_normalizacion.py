"""Tests del Punto 1: los emails nuevos se guardan siempre en minúscula y no se
pueden crear cuentas que difieran solo en mayúsculas/minúsculas."""

from django.test import TestCase

from users.models import Perfil, normalizar_email
from users.forms import PerfilCreateForm

PASS = "Milanesa2026!"


class NormalizacionEmailTests(TestCase):

    def test_normalizar_email_helper(self):
        self.assertEqual(normalizar_email("  Juan@Gmail.COM "), "juan@gmail.com")
        self.assertEqual(normalizar_email(None), "")

    def test_create_user_guarda_minuscula(self):
        u = Perfil.objects.create_user(email="Ana@Hotmail.com", password=PASS,
                                       first_name="Ana", last_name="B")
        self.assertEqual(u.email, "ana@hotmail.com")

    def test_save_directo_normaliza(self):
        u = Perfil(email="Pepe@X.COM", first_name="Pepe", last_name="P")
        u.set_password(PASS)
        u.save()
        self.assertEqual(Perfil.objects.get(pk=u.pk).email, "pepe@x.com")

    def test_form_registro_guarda_minuscula(self):
        form = PerfilCreateForm(data={
            "first_name": "Sol", "last_name": "G", "email": "Sol@Gmail.com",
            "password1": PASS, "password2": PASS,
        })
        self.assertTrue(form.is_valid(), form.errors)
        u = form.save()
        self.assertEqual(u.email, "sol@gmail.com")

    def test_form_rechaza_duplicado_por_mayusculas(self):
        Perfil.objects.create_user(email="dup@gmail.com", password=PASS,
                                   first_name="D", last_name="D")
        # Intento registrar la misma casilla con mayúsculas distintas
        form = PerfilCreateForm(data={
            "first_name": "Otro", "last_name": "Usuario", "email": "DUP@Gmail.com",
            "password1": PASS, "password2": PASS,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertEqual(Perfil.objects.filter(email__iexact="dup@gmail.com").count(), 1)

    def test_query_iexact_encuentra_variantes(self):
        Perfil.objects.create_user(email="mix@gmail.com", password=PASS,
                                   first_name="M", last_name="M")
        self.assertTrue(Perfil.objects.filter(email__iexact="MiX@Gmail.com").exists())
