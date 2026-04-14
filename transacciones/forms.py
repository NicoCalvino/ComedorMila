from django import forms
from transacciones.models import *
from decimal import Decimal
from django.core.validators import FileExtensionValidator

class TransaccionCompraForm(forms.ModelForm):
    numero_tarjeta = forms.CharField(
        label="Número de Tarjeta",
        max_length=19,
        required=True, # Obligatorio
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 123',
            'autofocus': 'autofocus',
            'pattern': '[0-9-]*',
            'autocomplete': 'off',
            'title': 'Solo números y guiones'
        })
    )

    class Meta:
        model = Transaccion
        fields = ["monto"]
        widgets = {
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1500.50', 'min': '0'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        monto = cleaned_data.get('monto')
        numero_tarjeta = cleaned_data.get('numero_tarjeta')
        
        if not numero_tarjeta:
            self.add_error('numero_tarjeta', "El número de tarjeta es obligatorio para realizar una compra.")
            return cleaned_data
        else:
            numero_tarjeta = str(numero_tarjeta).zfill(3)
    
        if not monto:
            return cleaned_data
        
        try:
            tarjeta_obj = Tarjeta.objects.get(codigo=numero_tarjeta)
        except Tarjeta.DoesNotExist:
            self.add_error('numero_tarjeta', "El número de tarjeta ingresado no existe.")
        
        if not tarjeta_obj.habilitada:
            self.add_error('numero_tarjeta', "Esta tarjeta se encuentra deshabilitada.")

        monto_decimal = Decimal(str(monto))

        nuevo_saldo = tarjeta_obj.saldo - monto_decimal
        limite_descubierto = Decimal(tarjeta_obj.cliente.limite)

        if nuevo_saldo < -Decimal(limite_descubierto):
            self.add_error('numero_tarjeta', f"Saldo insuficiente")

        cleaned_data['tarjeta_objeto'] = tarjeta_obj
        cleaned_data['nuevo_saldo_tarjeta'] = nuevo_saldo

        return cleaned_data
    
class TransaccionUpdateForm(forms.ModelForm):
    class Meta:
        model = Transaccion
        fields = ["monto"]
        widgets = {
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1500.50', 'min': '0'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        monto_nuevo = cleaned_data.get('monto')
                
        if not monto_nuevo:
            return cleaned_data
                
        transaccion_original = self.instance
        concepto_original = transaccion_original.concepto
        monto_original = transaccion_original.monto
        numero_tarjeta = transaccion_original.tarjeta.codigo

        tarjeta_obj = Tarjeta.objects.get(codigo=numero_tarjeta)
        
        monto_decimal = Decimal(str(monto_nuevo))

        if concepto_original == "COMPRA":
            nuevo_saldo = tarjeta_obj.saldo + monto_original - monto_decimal
        else:
            nuevo_saldo = tarjeta_obj.saldo - monto_original + monto_decimal

        if nuevo_saldo < Decimal('-2000'):
            self.add_error('monto', "Saldo insuficiente")

        cleaned_data['tarjeta_objeto'] = tarjeta_obj
        cleaned_data['nuevo_saldo_tarjeta'] = nuevo_saldo

        return cleaned_data
    
class TransaccionCargaForm(forms.ModelForm):
    numero_tarjeta = forms.CharField(
        label="Número de Tarjeta",
        max_length=19,
        required=True, # Obligatorio
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 123',
            'pattern': '[0-9-]*',
            'autocomplete': 'off',
            'autofocus': 'autofocus',
            'title': 'Solo números y guiones'
        })
    )

    class Meta:
        model = Transaccion
        fields = ["monto"]
        widgets = {
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1500.50', 'min': '0'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        monto = cleaned_data.get('monto')
        numero_tarjeta = cleaned_data.get('numero_tarjeta')
        
        if not numero_tarjeta:
            self.add_error('numero_tarjeta', "El número de tarjeta es obligatorio para realizar una carga.")
            return cleaned_data
        else:
            numero_tarjeta = str(numero_tarjeta).zfill(3)
            
        if not monto:
            return cleaned_data
        
        try:
            tarjeta_obj = Tarjeta.objects.get(codigo=numero_tarjeta)
        except Tarjeta.DoesNotExist:
            self.add_error('numero_tarjeta', "El número de tarjeta ingresado no existe.")
            return cleaned_data
        
        if not tarjeta_obj.habilitada:
            self.add_error('numero_tarjeta', "Esta tarjeta se encuentra deshabilitada.")
            return cleaned_data

        monto_decimal = Decimal(str(monto))

        nuevo_saldo = tarjeta_obj.saldo + monto_decimal

        cleaned_data['tarjeta_objeto'] = tarjeta_obj
        cleaned_data['nuevo_saldo_tarjeta'] = nuevo_saldo

        return cleaned_data
    
class SolicitudCargaForm(forms.ModelForm):
    class Meta:
        model = SolicitudCarga
        fields = ['comprobante']
        labels = {
            'comprobante': 'Subir comprobante de pago (Imagen/PDF)'
        }
        widgets = {
            # Esto ayuda a que el explorador de archivos del usuario filtre por defecto
            'comprobante': forms.FileInput(attrs={'accept': 'image/*,application/pdf'}),
        }

    # Agregamos una validación extra en el servidor para mayor seguridad
    comprobante = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        label='Subir comprobante de pago (Imagen/PDF)',
        required=True # O True, según prefieras
    )
