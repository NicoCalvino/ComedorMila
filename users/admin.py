from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from users.models import *
# Register your models here.

@admin.register(Perfil)
class PerfilAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('password',)}), # Si quitaste username en el modelo, quítalo de aquí
        ('Información Personal', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    #Columna visibles en la lista del modelo
    list_display = ("first_name", "last_name", "direccion", "celular")
    #Columnas con enlaces clickeables para entrar en el detalle
    list_display_links = ("first_name","last_name")
    #Campos por los que se puede buscar
    search_fields = ("first_name","last_name")
    #Orden por defecto
    ordering = ("first_name","last_name")

# @admin.register(Perfil)
# class PerfilAdmin(admin.ModelAdmin):
#     #Columna visibles en la lista del modelo
#     list_display = ("first_name", "last_name", "direccion", "celular")
#     #Columnas con enlaces clickeables para entrar en el detalle
#     list_display_links = ("first_name","last_name")
#     #Campos por los que se puede buscar
#     search_fields = ("first_name","last_name")
#     #Orden por defecto
#     ordering = ("first_name","last_name")