from django import forms
from menu.models import *
from django.utils import timezone
from datetime import date

class GeneracioMenuForm(forms.Form):
    fecha_inicial = forms.DateField(
        widget=forms.SelectDateWidget,
        label="Fecha de inicio (Lunes)"
    )
    semanas = forms.IntegerField(min_value=1, max_value=52, initial=2)

    def clean_fecha_inicial(self):
        fecha = self.cleaned_data['fecha_inicial']
        if fecha < timezone.now().date():
            raise forms.ValidationError("No puedes generar menús para fechas pasadas.")
        return fecha

class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ["fecha", "plato_principal", "plato_alternativo", "postre"]
        widgets = {
            'plato_principal': forms.Select(attrs={'class': 'form-control'}),
            'plato_alternativo': forms.Select(attrs={'class': 'form-control'}),
            'postre': forms.Select(attrs={'class': 'form-control'}),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['fecha'].widget.attrs['readonly'] = True
            # Opcionalmente, para mayor seguridad visual:
            # self.fields['fecha'].disabled = True  

class PlatoForm(forms.ModelForm):
    class Meta:
        model = Plato
        fields = ['nombre', 'categoria', 'ingrediente_principal', 'dia_fijo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Ravioles con tuco'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'ingrediente_principal': forms.Select(attrs={'class': 'form-control'}),
            'dia_fijo': forms.Select(attrs={'class': 'form-control'}),
        }

class FeriadoForm(forms.ModelForm):
    class Meta:
        model = Feriado
        fields = ['fecha', 'nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Día de la Bandera'}),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
        }
