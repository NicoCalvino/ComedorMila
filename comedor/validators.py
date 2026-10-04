"""Validación de los comprobantes de pago del comedor (imagen o PDF).

Antes los comprobantes eran ImageField y Pillow rechazaba los PDF. Ahora son
FileField, así que validamos acá: extensión permitida y que el contenido
coincida (un PDF real empieza con "%PDF-"; una imagen la tiene que poder
abrir Pillow).
"""
import os

from django.core.exceptions import ValidationError
from PIL import Image

EXTENSIONES_IMAGEN = ("jpg", "jpeg", "png", "webp")
EXTENSIONES_COMPROBANTE = EXTENSIONES_IMAGEN + ("pdf",)
# Para el atributo accept del <input type="file">.
ACCEPT_COMPROBANTE = "image/*,application/pdf"

MENSAJE_ERROR = "Subí una imagen (JPG, PNG) o un PDF del comprobante."


def validar_comprobante(archivo):
    nombre = getattr(archivo, "name", "") or ""
    ext = os.path.splitext(nombre)[1].lower().lstrip(".")
    if ext not in EXTENSIONES_COMPROBANTE:
        raise ValidationError(MENSAJE_ERROR, code="extension_invalida")

    try:
        archivo.seek(0)
        if ext == "pdf":
            if archivo.read(5) != b"%PDF-":
                raise ValidationError(
                    "El archivo no es un PDF válido o está dañado.", code="pdf_invalido"
                )
        else:
            Image.open(archivo).verify()
    except ValidationError:
        raise
    except Exception:
        raise ValidationError(
            "La imagen no es válida o está dañada.", code="imagen_invalida"
        )
    finally:
        try:
            archivo.seek(0)
        except Exception:
            pass
