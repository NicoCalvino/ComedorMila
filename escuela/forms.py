from django import forms
from escuela.models import *

class ColegioForm(forms.ModelForm):
    class Meta:
        model = Colegio
        fields = ["nombre"]

    def clean(self):
        cleaned_data = super().clean()
        colegio = cleaned_data.get("nombre")

        # Buscamos si ya existe un registro EXACTAMENTE igual
        if Colegio.objects.filter(
            nombre=colegio, 
        ).exists():
            raise forms.ValidationError(
                f"El colegio {colegio} ya esta dado de alta"
            )
        
        return cleaned_data
    

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ["curso","colegio","nivel","turno"]

        widgets = {
            'curso':forms.TextInput(attrs={'class':'form-control'}),
            'nivel':forms.Select(attrs={'class':'form-control'}),
            'colegio':forms.Select(attrs={'class':'form-control'}),
            'turno':forms.TimeInput(attrs={'class':'form-control', 'type':'time'}, format='%H:%M'),
        }

    def clean(self):
        cleaned_data = super().clean()
        colegio = cleaned_data.get("colegio")
        nivel = cleaned_data.get("nivel")
        curso = cleaned_data.get("curso")

        # Buscamos si ya existe un registro EXACTAMENTE igual
        queryset = Curso.objects.filter(
            colegio=colegio, 
            nivel=nivel, 
            curso=curso, 
        )

        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError(
                "Ya existe un registro con estos mismos datos exactos."
            )
        
        return cleaned_data
    
class ClienteForm(forms.ModelForm):
    colegio = forms.ModelChoiceField(
        queryset=Colegio.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Colegio"
    )


    class Meta:
        model = Cliente
        fields = [
            "nombre",
            "apellido",
            "colegio",
            "curso",
            "limite",
        ]
        widgets = {
            'nombre':forms.TextInput(attrs={'class':'form-control'}),
            'apellido':forms.TextInput(attrs={'class':'form-control'}),
            'limite':forms.NumberInput(attrs={'class':'form-control'}),
            'curso':forms.Select(attrs={'class':'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and not self.user.is_superuser:
            self.fields.pop('limite')

        # Esta es la clave: personalizamos la etiqueta del campo curso
        self.fields['curso'].label_from_instance = lambda obj: f"{obj.curso}"

        if self.instance and self.instance.pk:
            self.initial['colegio'] = self.instance.curso.colegio.pk
            self.fields['curso'].queryset = Curso.objects.filter(
                colegio=self.instance.curso.colegio
            ).order_by('nivel', 'curso')
        else:
            self.fields['curso'].queryset = Curso.objects.none()
        
        # 2. Lógica para cuando el formulario falla y se vuelve a cargar (POST)
        if 'colegio' in self.data:
            try:
                colegio_id = int(self.data.get('colegio'))
                self.fields['curso'].queryset = Curso.objects.filter(
                    colegio_id=colegio_id
                ).order_by('nivel', 'curso')
            except (ValueError, TypeError):
                pass


class MovimientoColegioForm(forms.ModelForm):
    """Alta y edición de movimientos de la cuenta del colegio.

    Reglas: un solo canon por colegio por mes, y no se puede tocar un mes
    marcado como pagado (ni mover un movimiento hacia/desde uno).
    """
    class Meta:
        model = MovimientoColegio
        fields = ["tipo", "fecha", "concepto", "monto"]
        widgets = {
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "concepto": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: Café sala de profesores"}),
            "monto": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
        }

    def __init__(self, *args, colegio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.colegio = colegio or (self.instance.colegio if self.instance.pk else None)
        # Fecha original (antes de aplicar lo que viene en el POST).
        self._fecha_original = self.instance.fecha if self.instance.pk else None

    def clean(self):
        from escuela.cuenta_colegio import mes_pagado, nombre_mes
        cleaned_data = super().clean()
        fecha = cleaned_data.get("fecha")
        tipo = cleaned_data.get("tipo")
        if not fecha or self.colegio is None:
            return cleaned_data

        if self._fecha_original and mes_pagado(self.colegio, self._fecha_original.year, self._fecha_original.month):
            raise forms.ValidationError(
                f"{nombre_mes(self._fecha_original.year, self._fecha_original.month)} está marcado como pagado. "
                "Desmarcalo para poder modificar sus movimientos."
            )
        if mes_pagado(self.colegio, fecha.year, fecha.month):
            raise forms.ValidationError(
                f"{nombre_mes(fecha.year, fecha.month)} está marcado como pagado. "
                "Desmarcalo para poder cargar movimientos en ese mes."
            )

        if tipo == MovimientoColegio.CANON:
            otros = MovimientoColegio.objects.filter(
                colegio=self.colegio, tipo=MovimientoColegio.CANON,
                fecha__year=fecha.year, fecha__month=fecha.month,
            )
            if self.instance.pk:
                otros = otros.exclude(pk=self.instance.pk)
            if otros.exists():
                raise forms.ValidationError(
                    f"Ya hay un canon cargado para {nombre_mes(fecha.year, fecha.month)}. "
                    "Editá ese en lugar de cargar otro."
                )
        return cleaned_data
