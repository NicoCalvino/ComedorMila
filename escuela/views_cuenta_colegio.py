"""Cuenta corriente mensual del colegio (consumos vs. canon de concesión)."""
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from escuela.cuenta_colegio import (
    mes_anterior, mes_pagado, mes_siguiente, nombre_mes, resumen_mes,
)
from escuela.forms import MovimientoColegioForm
from escuela.models import Colegio, MesColegioPagado, MovimientoColegio


class _SoloSuperusuario(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, "Acceso restringido solo para administradores.")
        return redirect("home")


def _periodo(datos):
    """(year, month) pedido; por defecto el mes en curso."""
    hoy = timezone.localdate()
    try:
        year = int(datos.get("year"))
        month = int(datos.get("month"))
        if not (1 <= month <= 12 and 2020 <= year <= 2100):
            raise ValueError
    except (TypeError, ValueError):
        return hoy.year, hoy.month
    return year, month


def _colegio(datos):
    """Colegio elegido; si hay uno solo (o no se eligió), el primero."""
    colegios = Colegio.objects.order_by("nombre")
    colegio_id = datos.get("colegio")
    if colegio_id:
        try:
            return colegios.filter(pk=int(colegio_id)).first() or colegios.first()
        except (TypeError, ValueError):
            pass
    return colegios.first()


def _url_mes(colegio, year, month):
    return reverse("cuenta_colegio") + "?" + urlencode(
        {"colegio": colegio.pk, "year": year, "month": month})


class CuentaColegioView(_SoloSuperusuario, View):
    template_name = "escuela/cuenta_colegio.html"

    def _render(self, request, colegio, year, month, form):
        contexto = {
            "colegios": Colegio.objects.order_by("nombre"),
            "colegio": colegio,
            "year": year,
            "month": month,
            "titulo_mes": nombre_mes(year, month) if colegio else "",
            "form": form,
        }
        if colegio:
            contexto.update(resumen_mes(colegio, year, month))
            contexto["anterior"] = mes_anterior(year, month)
            contexto["siguiente"] = mes_siguiente(year, month)
            if contexto["neto"] is not None:
                contexto["neto_abs"] = abs(contexto["neto"])
        return render(request, self.template_name, contexto)

    def get(self, request):
        colegio = _colegio(request.GET)
        year, month = _periodo(request.GET)
        hoy = timezone.localdate()
        # Fecha sugerida: hoy si se está viendo el mes en curso, si no el día 1.
        fecha = hoy if (year, month) == (hoy.year, hoy.month) else hoy.replace(year=year, month=month, day=1)
        form = MovimientoColegioForm(colegio=colegio, initial={"fecha": fecha})
        return self._render(request, colegio, year, month, form)

    def post(self, request):
        colegio = _colegio(request.POST)
        if colegio is None:
            messages.error(request, "Primero hay que dar de alta un colegio.")
            return redirect("cuenta_colegio")
        form = MovimientoColegioForm(request.POST, colegio=colegio)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.colegio = colegio
            mov.registrado_por = request.user
            mov.save()
            messages.success(request, f"{mov.get_tipo_display()} de $ {mov.monto} registrado.")
            return redirect(_url_mes(colegio, mov.fecha.year, mov.fecha.month))
        year, month = _periodo(request.POST)
        return self._render(request, colegio, year, month, form)


class EditarMovimientoColegioView(_SoloSuperusuario, View):
    template_name = "escuela/editar_movimiento_colegio.html"

    def get(self, request, pk):
        mov = get_object_or_404(MovimientoColegio, pk=pk)
        return render(request, self.template_name, {
            "mov": mov, "form": MovimientoColegioForm(instance=mov),
            "volver": _url_mes(mov.colegio, mov.fecha.year, mov.fecha.month),
        })

    def post(self, request, pk):
        mov = get_object_or_404(MovimientoColegio, pk=pk)
        volver = _url_mes(mov.colegio, mov.fecha.year, mov.fecha.month)
        form = MovimientoColegioForm(request.POST, instance=mov)
        if form.is_valid():
            mov = form.save()
            messages.success(request, "Movimiento actualizado.")
            return redirect(_url_mes(mov.colegio, mov.fecha.year, mov.fecha.month))
        return render(request, self.template_name, {"mov": mov, "form": form, "volver": volver})


class EliminarMovimientoColegioView(_SoloSuperusuario, View):
    def post(self, request, pk):
        mov = get_object_or_404(MovimientoColegio, pk=pk)
        volver = _url_mes(mov.colegio, mov.fecha.year, mov.fecha.month)
        if mes_pagado(mov.colegio, mov.fecha.year, mov.fecha.month):
            messages.error(request, f"{nombre_mes(mov.fecha.year, mov.fecha.month)} está marcado como pagado. "
                                    "Desmarcalo para poder borrar movimientos.")
        else:
            mov.delete()
            messages.success(request, "Movimiento eliminado.")
        return redirect(volver)


class MarcarMesPagadoColegioView(_SoloSuperusuario, View):
    def post(self, request):
        colegio = _colegio(request.POST)
        year, month = _periodo(request.POST)
        if colegio is None:
            return redirect("cuenta_colegio")
        volver = _url_mes(colegio, year, month)
        resumen = resumen_mes(colegio, year, month)
        if resumen["pagado"]:
            messages.info(request, f"{nombre_mes(year, month)} ya estaba marcado como pagado.")
        elif resumen["canon"] is None:
            messages.error(request, "Cargá el canon del mes antes de marcarlo como pagado.")
        else:
            try:
                MesColegioPagado.objects.create(
                    colegio=colegio, year=year, month=month,
                    monto_pagado=resumen["neto"], registrado_por=request.user,
                )
                messages.success(request, f"{nombre_mes(year, month)} marcado como pagado.")
            except IntegrityError:
                messages.info(request, f"{nombre_mes(year, month)} ya estaba marcado como pagado.")
        return redirect(volver)


class DesmarcarMesPagadoColegioView(_SoloSuperusuario, View):
    def post(self, request):
        colegio = _colegio(request.POST)
        year, month = _periodo(request.POST)
        if colegio is None:
            return redirect("cuenta_colegio")
        borrados, _ = MesColegioPagado.objects.filter(colegio=colegio, year=year, month=month).delete()
        if borrados:
            messages.success(request, f"{nombre_mes(year, month)} vuelve a estar abierto para cambios.")
        return redirect(_url_mes(colegio, year, month))
