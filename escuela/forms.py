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
        fields = ["curso","colegio","nivel"]

        widgets = {
            'curso':forms.TextInput(attrs={'class':'form-control'}),
            'nivel':forms.Select(attrs={'class':'form-control'}),
            'colegio':forms.Select(attrs={'class':'form-control'}),
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
        super().__init__(*args, **kwargs)
        
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