"""Regla de permiso para la suplantación de usuarios (django-hijack).

Quién puede suplantar y a quién:
- Suplantador (hijacker): debe ser superusuario.
- Suplantado (hijacked): debe ser una FAMILIA, es decir un usuario común
  (no staff, no superusuario) que tenga al menos un hijo/alumno cargado.

De esta forma un admin nunca puede "entrar" a la cuenta de otro admin ni a un
perfil suelto sin alumnos: solo a las familias.
"""


def solo_familias(*, hijacker, hijacked):
    if hijacker is None or hijacked is None:
        return False
    if not hijacker.is_superuser:
        return False
    if hijacked.pk == hijacker.pk:
        return False
    # El objetivo no puede ser otro administrador.
    if hijacked.is_staff or hijacked.is_superuser:
        return False
    # Debe ser una familia: tener al menos un alumno (Cliente) asociado.
    return hijacked.clientes.exists()
