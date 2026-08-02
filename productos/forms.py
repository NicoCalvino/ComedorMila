from django import forms
from productos.models import *

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            "nombre",
            "marca",
            "categoria",
            "precio",
            "stock",
            "codigo_de_barras",
            "picture"
        ]
        widgets = {
            'picture': forms.FileInput(attrs={"class": "form-control"}),
            'nombre':forms.TextInput(attrs={'class':'form-control'}),
            'marca':forms.TextInput(attrs={'class':'form-control'}),
            'categoria':forms.Select(attrs={'class':'form-control'}),
            'precio':forms.NumberInput(attrs={'class':'form-control'}),
            'stock':forms.NumberInput(attrs={'class':'form-control'}),
            'codigo_de_barras':forms.TextInput(attrs={'class':'form-control'}),
        }

    def clean_codigo_de_barras(self):
        codigo = (self.cleaned_data.get("codigo_de_barras") or "").strip()

        if not codigo:
            raise forms.ValidationError("Ingresá un código de barras.")

        if not codigo.isdigit():
            raise forms.ValidationError("El código de barras debe contener solo números.")

        # Chequeo de duplicado con mensaje claro (excluyendo el propio producto al editar)
        duplicados = Producto.objects.filter(codigo_de_barras=codigo)
        if self.instance and self.instance.pk:
            duplicados = duplicados.exclude(pk=self.instance.pk)
        if duplicados.exists():
            raise forms.ValidationError(
                f'Ya existe un producto con el código de barras "{codigo}". Usá uno distinto.'
            )

        return codigo
