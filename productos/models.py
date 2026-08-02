from django.db import models
from django.core.validators import MinValueValidator
import uuid

def generate_code():
    return uuid.uuid4().hex

def picture_upload_to(instance, filename):
    return f"productos/{instance.marca}/{filename}"

class Producto(models.Model):
    CATEGORIAS = (
        ("ALFAJORES", "Alfajores"),
        ("BEBIDAS", "Bebidas"),
        ("GALLETITAS", "Galletitas"),
        ("COMIDA", "Comida"),
        ("CHOCOLATES", "Chocolates"),
        ("CARAMELOS", "Caramelos"),
        ("HELADOS", "Helados"),
    )
    picture = models.ImageField(
        upload_to=picture_upload_to,
        verbose_name="Picture",
        blank=True
    )
    nombre = models.CharField(max_length=50, null=False)
    marca = models.CharField(max_length=30, null=False)
    categoria = models.CharField(choices=CATEGORIAS, max_length=30, null=False)
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    codigo_de_barras = models.CharField(max_length=13, null=False, unique=True)
    code = models.CharField(max_length=32,
                            unique=True,
                            default = generate_code
                            )
    def __str__(self):
        return f"{self.nombre} {self.marca}/ Precio: $ {self.precio}/ Stock: {self.stock}"    
