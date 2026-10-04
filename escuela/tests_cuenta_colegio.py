from datetime import date
from decimal import Decimal

from django.conf import settings as dj_settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from escuela.cuenta_colegio import resumen_mes
from escuela.forms import MovimientoColegioForm
from escuela.models import Colegio, MesColegioPagado, MovimientoColegio
from users.models import Perfil

MB = 'django.contrib.auth.backends.ModelBackend'
_MW_SIN_OTP = [m for m in dj_settings.MIDDLEWARE if m != 'main.middleware.StaffOTPRequiredMiddleware']

CONSUMO = MovimientoColegio.CONSUMO
CANON = MovimientoColegio.CANON


class ResumenMesTest(TestCase):
    def setUp(self):
        self.col = Colegio.objects.create(nombre="Mila")

    def _mov(self, tipo, monto, fecha):
        return MovimientoColegio.objects.create(
            colegio=self.col, tipo=tipo, concepto="x", monto=Decimal(monto), fecha=fecha)

    def test_neto_es_canon_menos_consumos_del_mes(self):
        self._mov(CONSUMO, "1000", date(2026, 9, 3))
        self._mov(CONSUMO, "2500.50", date(2026, 9, 20))
        self._mov(CANON, "50000", date(2026, 9, 30))
        self._mov(CONSUMO, "9999", date(2026, 10, 1))   # otro mes: no cuenta
        r = resumen_mes(self.col, 2026, 9)
        self.assertEqual(r["consumos"], Decimal("3500.50"))
        self.assertEqual(r["canon"], Decimal("50000"))
        self.assertEqual(r["neto"], Decimal("46499.50"))
        self.assertEqual(r["movimientos"].count(), 3)

    def test_sin_canon_el_neto_queda_pendiente(self):
        self._mov(CONSUMO, "1000", date(2026, 9, 3))
        r = resumen_mes(self.col, 2026, 9)
        self.assertIsNone(r["canon"])
        self.assertIsNone(r["neto"])

    def test_neto_negativo_si_consumos_superan_canon(self):
        self._mov(CONSUMO, "8000", date(2026, 9, 3))
        self._mov(CANON, "5000", date(2026, 9, 30))
        self.assertEqual(resumen_mes(self.col, 2026, 9)["neto"], Decimal("-3000"))


class MovimientoColegioFormTest(TestCase):
    def setUp(self):
        self.col = Colegio.objects.create(nombre="Mila")

    def _form(self, tipo, fecha, monto="100", instance=None):
        return MovimientoColegioForm(
            {"tipo": tipo, "fecha": fecha, "concepto": "c", "monto": monto},
            colegio=self.col, instance=instance)

    def test_un_solo_canon_por_mes(self):
        MovimientoColegio.objects.create(colegio=self.col, tipo=CANON, concepto="c",
                                         monto=Decimal("1"), fecha=date(2026, 9, 1))
        self.assertFalse(self._form(CANON, "2026-09-30").is_valid())
        self.assertTrue(self._form(CANON, "2026-10-01").is_valid())
        self.assertTrue(self._form(CONSUMO, "2026-09-30").is_valid())

    def test_editar_el_canon_existente_es_valido(self):
        canon = MovimientoColegio.objects.create(colegio=self.col, tipo=CANON, concepto="c",
                                                 monto=Decimal("1"), fecha=date(2026, 9, 1))
        self.assertTrue(self._form(CANON, "2026-09-15", monto="2", instance=canon).is_valid())

    def test_monto_debe_ser_positivo_y_dentro_del_tope(self):
        self.assertFalse(self._form(CONSUMO, "2026-09-01", monto="0").is_valid())
        self.assertFalse(self._form(CONSUMO, "2026-09-01", monto="-5").is_valid())
        self.assertFalse(self._form(CONSUMO, "2026-09-01", monto="100000000").is_valid())
        self.assertTrue(self._form(CONSUMO, "2026-09-01", monto="99999999.99").is_valid())

    def test_mes_pagado_bloquea_altas_y_ediciones(self):
        mov = MovimientoColegio.objects.create(colegio=self.col, tipo=CONSUMO, concepto="c",
                                               monto=Decimal("1"), fecha=date(2026, 9, 1))
        MesColegioPagado.objects.create(colegio=self.col, year=2026, month=9, monto_pagado=Decimal("0"))
        self.assertFalse(self._form(CONSUMO, "2026-09-10").is_valid())
        # No se puede editar uno del mes pagado, ni sacarlo de ese mes.
        self.assertFalse(self._form(CONSUMO, "2026-09-01", monto="5", instance=mov).is_valid())
        self.assertFalse(self._form(CONSUMO, "2026-10-01", instance=mov).is_valid())
        # Otro mes sigue abierto.
        self.assertTrue(self._form(CONSUMO, "2026-10-10").is_valid())


@override_settings(MIDDLEWARE=_MW_SIN_OTP)
class CuentaColegioViewsTest(TestCase):
    def setUp(self):
        self.admin = Perfil.objects.create_user(
            email="admin@t.com", password="x", first_name="Super", last_name="User",
            is_superuser=True, is_staff=True)
        self.padre = Perfil.objects.create_user(
            email="padre@t.com", password="x", first_name="Ana", last_name="Perez")
        self.col = Colegio.objects.create(nombre="Mila")
        self.c = Client()
        self.c.force_login(self.admin, backend=MB)

    def _post_mov(self, tipo, fecha, monto, concepto="c"):
        return self.c.post(reverse("cuenta_colegio"), {
            "colegio": self.col.pk, "year": 2026, "month": 9,
            "tipo": tipo, "fecha": fecha, "concepto": concepto, "monto": monto})

    def test_solo_superusuario(self):
        c = Client()
        c.force_login(self.padre, backend=MB)
        r = c.get(reverse("cuenta_colegio"))
        self.assertRedirects(r, reverse("home"), fetch_redirect_response=False)

    def test_carga_y_muestra_el_neto(self):
        self._post_mov(CONSUMO, "2026-09-05", "1500", "Café profesores")
        self._post_mov(CANON, "2026-09-30", "40000", "Canon septiembre")
        mov = MovimientoColegio.objects.get(concepto="Café profesores")
        self.assertEqual(mov.colegio, self.col)
        self.assertEqual(mov.registrado_por, self.admin)
        r = self.c.get(reverse("cuenta_colegio"), {"colegio": self.col.pk, "year": 2026, "month": 9})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["neto"], Decimal("38500"))
        self.assertContains(r, "Café profesores")
        self.assertContains(r, "Marcar mes como pagado")

    def test_segundo_canon_no_se_guarda(self):
        self._post_mov(CANON, "2026-09-30", "40000")
        r = self._post_mov(CANON, "2026-09-15", "1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(MovimientoColegio.objects.filter(tipo=CANON).count(), 1)
        self.assertContains(r, "Ya hay un canon cargado")

    def test_editar_y_eliminar(self):
        self._post_mov(CONSUMO, "2026-09-05", "1500")
        mov = MovimientoColegio.objects.get()
        self.c.post(reverse("editar_movimiento_colegio", args=[mov.pk]),
                    {"tipo": CONSUMO, "fecha": "2026-09-06", "concepto": "nuevo", "monto": "2000"})
        mov.refresh_from_db()
        self.assertEqual((mov.concepto, mov.monto, mov.fecha), ("nuevo", Decimal("2000"), date(2026, 9, 6)))
        self.c.post(reverse("eliminar_movimiento_colegio", args=[mov.pk]))
        self.assertFalse(MovimientoColegio.objects.exists())

    def test_marcar_pagado_requiere_canon_y_bloquea(self):
        datos = {"colegio": self.col.pk, "year": 2026, "month": 9}
        self._post_mov(CONSUMO, "2026-09-05", "1500")
        self.c.post(reverse("marcar_mes_pagado_colegio"), datos)
        self.assertFalse(MesColegioPagado.objects.exists())   # sin canon no se puede

        self._post_mov(CANON, "2026-09-30", "40000")
        self.c.post(reverse("marcar_mes_pagado_colegio"), datos)
        pagado = MesColegioPagado.objects.get()
        self.assertEqual(pagado.monto_pagado, Decimal("38500"))

        # Bloqueado: no se puede cargar, borrar ni editar.
        self._post_mov(CONSUMO, "2026-09-10", "100")
        self.assertEqual(MovimientoColegio.objects.count(), 2)
        consumo = MovimientoColegio.objects.get(tipo=CONSUMO)
        self.c.post(reverse("eliminar_movimiento_colegio", args=[consumo.pk]))
        self.assertTrue(MovimientoColegio.objects.filter(pk=consumo.pk).exists())
        r = self.c.get(reverse("cuenta_colegio"), datos)
        self.assertContains(r, "Desmarcar pagado")
        self.assertNotContains(r, "Nuevo movimiento")

        # Desmarcar lo vuelve a abrir.
        self.c.post(reverse("desmarcar_mes_pagado_colegio"), datos)
        self.assertFalse(MesColegioPagado.objects.exists())
        self.c.post(reverse("eliminar_movimiento_colegio", args=[consumo.pk]))
        self.assertFalse(MovimientoColegio.objects.filter(pk=consumo.pk).exists())

    def test_tarjeta_en_inicio_admin(self):
        r = self.c.get(reverse("home"))
        self.assertContains(r, reverse("cuenta_colegio"))
