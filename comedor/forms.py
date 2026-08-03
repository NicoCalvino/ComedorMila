from django import forms
from comedor.models import *
from users.models import Perfil
from datetime import date
from decimal import Decimal


class RegistrarPagoAdminComedorForm(forms.Form):
    """Admin: carga un pago de comedor a nombre de una familia (por ejemplo
    cuando mandan el comprobante por WhatsApp). El comprobante es opcional."""

    familia = forms.ModelChoiceField(
        queryset=Perfil.objects.filter(
            clientes__isnull=False, is_superuser=False,
        ).distinct().order_by('last_name', 'first_name'),
        label="Familia",
        empty_label="Elegí una familia…",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'select-familia'}),
    )
    monto = forms.DecimalField(
        max_digits=12, decimal_places=2,
        label="Monto pagado",
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 'min': '1', 'step': '0.01',
            'placeholder': 'Monto pagado',
        }),
    )
    comprobante = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        label="Comprobante (opcional)",
        help_text="Si te mandaron la foto del pago por WhatsApp, subila acá.",
    )

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto is None or monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a cero.")
        return monto


class SolicitudPagoComedorForm(forms.ModelForm):
    comprobante = forms.ImageField(
        required=True,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        label="Comprobante (foto de la transferencia/pago)",
    )

    class Meta:
        model = SolicitudPagoComedor
        fields = ['monto', 'comprobante']
        widgets = {
            'monto': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'step': '0.01',
                'placeholder': 'Monto pagado',
            }),
        }

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto is None or monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a cero.")
        return monto

class PrecioForm(forms.ModelForm):
    class Meta:
        model = Precio
        fields = ["colegio", "alm_por_sem","nivel","nro_de_cliente","precio"]
        widgets = {
            'colegio':forms.Select(attrs={'class': 'form-select', 'autofocus': 'autofocus'}),
            'alm_por_sem':forms.NumberInput(attrs={'class':'form-control'}),
            'nivel':forms.Select(attrs={'class': 'form-select'}),
            'nro_de_cliente':forms.NumberInput(attrs={'class':'form-control'}),
            'precio':forms.NumberInput(attrs={'class':'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        colegio = cleaned_data.get("colegio")
        nivel = cleaned_data.get("nivel")
        alm_por_sem = cleaned_data.get("alm_por_sem")
        nro_de_cliente = cleaned_data.get("nro_de_cliente")

        if alm_por_sem > 5:
            raise forms.ValidationError(
                "No pueden ser mas de 5 almuerzos por semana"
            )
        
        if nro_de_cliente > 3:
            raise forms.ValidationError(
                "El número máximo de clientes es 3"
            )

        # Buscamos si ya existe un registro EXACTAMENTE igual
        queryset = Precio.objects.filter(
            colegio=colegio,
            nivel=nivel,
            alm_por_sem=alm_por_sem,
            nro_de_cliente=nro_de_cliente,
        )

        # SI ESTAMOS EDITANDO: Excluimos el registro actual de la búsqueda de duplicados
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError(
                "Ya existe un registro con estos mismos datos exactos."
            )
        
        return cleaned_data

class ValeMensualForm(forms.ModelForm):
    class Meta:
        model = ValeMensual
        fields = ["lunes", "martes", "miercoles", "jueves", "viernes", "comentarios"]
        widgets = {
            'lunes': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'martes': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'miercoles': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'jueves': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'viernes': forms.CheckboxInput(attrs={'class': 'form-check-input', 'role': 'switch'}),
            'comentarios': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Sin sal, vegetariano, etc.'}),
        }
        
class ValeDiarioForm(forms.ModelForm):
    class Meta:
        model = ValeDiario
        fields = ['fecha', 'comprobante','comentarios'] # Reemplaza con los nombres reales de tus campos
        widgets = {
            # type='date' le dice al navegador que muestre un calendario interactivo
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'min': date.today().isoformat()}),
            # form-control en un FileInput hace que el botón de subir archivo se vea estilo Bootstrap
            'comprobante': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'comentarios': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Sin sal, vegetariano, etc.'}),
        }

    def __init__(self, *args, **kwargs):
        # Extraemos el cliente_id enviado desde la vista
        self.cliente_id = kwargs.pop('cliente_id', None)
        super().__init__(*args, **kwargs)

    def clean_fecha(self):
        fecha_ingresada = self.cleaned_data.get('fecha')
        
        if fecha_ingresada < date.today():
            raise forms.ValidationError("No se pueden cargar vales para días que ya pasaron.")
        
        if fecha_ingresada.weekday() >= 5:
            raise forms.ValidationError("No se pueden cargar vales para fin de semana.")

        if fecha_ingresada and self.cliente_id:
            # Validamos: ¿Este cliente específico ya tiene un vale esta fecha?
            existe = ValeDiario.objects.filter(
                cliente_id=self.cliente_id, 
                fecha=fecha_ingresada,
                cancelado=False
            ).exists()
            
            if existe:
                raise forms.ValidationError(
                    f"Este cliente ya tiene un vale cargado para el día {fecha_ingresada}."
                )

        return fecha_ingresada