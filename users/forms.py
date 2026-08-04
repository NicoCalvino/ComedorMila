from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from users.models import Perfil, normalizar_email


def _validar_email_unico(email, instance=None):
    """Normaliza el email y verifica que no exista otro igual sin importar
    mayúsculas/minúsculas. Devuelve el email normalizado o lanza ValidationError
    con un mensaje claro para el usuario."""
    email = normalizar_email(email)
    if not email:
        raise forms.ValidationError("El email es obligatorio.")
    qs = Perfil.objects.filter(email__iexact=email)
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise forms.ValidationError("Ya existe una cuenta registrada con ese email.")
    return email


class PerfilCreateForm(UserCreationForm):
    class Meta:
        model = Perfil
        fields = ("first_name","last_name", "email")

        widgets = {
            "first_name":forms.TextInput(attrs={'autofocus': True, "class": "form-control"}),
            "last_name":forms.TextInput(attrs={"class": "form-control"}),
            "email":forms.EmailInput(attrs={"class": "form-control"}),
            "celular":forms.NumberInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        return _validar_email_unico(self.cleaned_data.get("email"), self.instance)

class PerfilChangeForm(UserChangeForm):
    class Meta:
        model = Perfil
        fields = ("avatar", "direccion", "celular", "first_name", "last_name")

        widgets = {
            "avatar": forms.FileInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "celular":forms.NumberInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }

class PerfilAdminChangeForm(UserChangeForm):
    class Meta:
        model = Perfil
        fields = ("avatar", "direccion", "celular", "first_name", "last_name", "email")

        widgets = {
            "avatar": forms.FileInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "email":forms.EmailInput(attrs={"class": "form-control"}),
            "celular":forms.NumberInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        return _validar_email_unico(self.cleaned_data.get("email"), self.instance)