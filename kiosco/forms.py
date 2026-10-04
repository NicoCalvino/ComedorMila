from datetime import date
from django import forms
from kiosco.models import *

class TarjetaForm(forms.ModelForm):
    class Meta:
        model = Tarjeta
        fields = [
            "codigo"
        ]
        widgets = {
            'codigo':forms.TextInput(attrs={'class':'form-control'}),
        }

class TarjetasMasivoForm(forms.Form):
    numero_desde = forms.IntegerField(
        label='Número Desde',
        required=True,
        min_value=1,
        max_value=999,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', # <-- ESTO ES CLAVE PARA EL DISEÑO
            'placeholder': 'Ej: 1',
            'min': '1',    # <-- Mínimo en Frontend (HTML)
            'max': '999'   # <-- Máximo en Frontend (HTML)
        })
    )
    numero_hasta = forms.IntegerField(
        label='Número Hasta',
        required=True,
        min_value=1,
        max_value=999,
        widget=forms.NumberInput(attrs={
            'class': 'form-control', # <-- ESTO ES CLAVE PARA EL DISEÑO
            'placeholder': 'Ej: 999',
            'min': '1',    # <-- Mínimo en Frontend (HTML)
            'max': '999'   # <-- Máximo en Frontend (HTML)
        })
    )
    
    # Validar que "desde" no sea mayor que "hasta"
    def clean(self):
        cleaned_data = super().clean()
        desde = cleaned_data.get("numero_desde")
        hasta = cleaned_data.get("numero_hasta")

        if desde and hasta and desde > hasta:
            raise forms.ValidationError("El número 'Desde' no puede ser mayor que el número 'Hasta'.")
        return cleaned_data


# class TarjetaUpdateForm(forms.ModelForm):
#     class Meta:
#         model = Tarjeta
#         fields = [
#             "habilitada"
#         ]
#         widgets = {
#             'habilitada':forms.Select(attrs={'class':'form-control'}),
#         }

# class TarjetaSaldoForm(forms.ModelForm):
#     class Meta:
#         model = Tarjeta
#         fields = ["saldo"]
#         widgets = {
#             'saldo':forms.NumberInput(attrs={'class':'form-control'}),
#         }


class RecaudacionEfectivoForm(forms.ModelForm):
    class Meta:
        model = RecaudacionEfectivo
        fields = ["fecha", "monto", "observaciones"]
        labels = {
            "fecha": "Fecha",
            "monto": "Total en efectivo",
            "observaciones": "Observaciones (opcional)",
        }
        widgets = {
            "fecha": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "monto": forms.NumberInput(attrs={
                "class": "form-control", "min": "0.01", "step": "0.01",
                "max": "99999999.99", "placeholder": "0,00",
            }),
            "observaciones": forms.TextInput(attrs={
                "class": "form-control", "maxlength": "200",
                "placeholder": "Ej.: faltó cambio, se cerró temprano…",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].widget.attrs["max"] = date.today().isoformat()
        if not self.instance.pk and not self.is_bound:
            self.initial.setdefault("fecha", date.today())

    def clean_fecha(self):
        fecha = self.cleaned_data.get("fecha")
        if fecha and fecha > date.today():
            raise forms.ValidationError("No se puede cargar la recaudación de un día que todavía no pasó.")
        return fecha

    def clean_monto(self):
        monto = self.cleaned_data.get("monto")
        if monto is not None and monto > RecaudacionEfectivo.MONTO_MAXIMO:
            raise forms.ValidationError("El monto es demasiado alto. Revisá que esté bien escrito.")
        return monto

    def clean_observaciones(self):
        return (self.cleaned_data.get("observaciones") or "").strip()
