from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib.auth import login, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required, user_passes_test
import pandas as pd

from django.core.exceptions import PermissionDenied
from users.forms import *
from users.models import *

# Registrarse
def register(request):
    if request.method == "POST":
        form = PerfilCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('perfil_detail')
    else:
        form = PerfilCreateForm()
    return render(request, "users/register.html", {"form": form})

# Lista de Usuarios
@user_passes_test(lambda u: u.is_superuser)
def lista_usuarios(request):
    busqueda = request.GET.get("buscador") 
    filtro = request.GET.get('filtro', 'normales')
    usuarios_query = Perfil.objects.all()

    if busqueda:
        usuarios_query = Perfil.objects.filter(
            Q(first_name__icontains = busqueda) | Q(last_name__icontains=busqueda) | Q(email__icontains=busqueda),
        )

    if filtro == 'normales':
        usuarios_query = usuarios_query.filter(is_superuser=False)
    elif filtro == 'superusuarios':
        usuarios_query = usuarios_query.filter(is_superuser=True)


    return render(request, 'users/lista_usuarios.html',{"usuarios":usuarios_query})

# Archivo Subida Usuarios
@user_passes_test(lambda u: u.is_superuser)
def importar_usuarios_excel(request):
    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        excel_file = request.FILES['archivo_excel']
        
        # Validar extensión
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "Por favor, sube un archivo Excel válido.")
            return redirect('lista_usuarios')

        try:
            # Leer el excel con pandas
            df = pd.read_excel(excel_file)
            df = df.fillna('') # Evitar errores de NaN con strings
            
            resultados = {
                'exitos': 0,
                'errores': [],
                'total': len(df),
                'proceso': 'Importación de Usuarios',
                'url_retorno': 'lista_usuarios'
            }

            for index, row in df.iterrows():
                email = str(row.get('email', '')).strip()
                password = str(row.get('password', ''))
                
                try:
                    if Perfil.objects.filter(email=email).exists():
                        resultados['errores'].append({
                            'fila': index + 2,
                            'identificador': email,
                            'mensaje': "El email ya está registrado."
                        })
                        continue

                    Perfil.objects.create_user(                        
                        email=email,
                        password=password,
                        first_name=row.get('first_name', ''),
                        last_name=row.get('last_name', ''),
                        direccion=row.get('direccion', ''),
                        celular=row.get('celular', '')
                        )
                    resultados['exitos'] += 1

                except Exception as e:
                    resultados['errores'].append({
                        'fila': index + 2,
                        'identificador': email,
                        'mensaje': str(e)
                    })

            request.session['ultimo_resultado_importacion'] = resultados
            return redirect('resultado_importacion')

        except Exception as e:
            messages.error(request, f"Error crítico: {e}")
            return redirect('lista_usuarios')

    return redirect('lista_usuarios')

# Ver Perfil
@login_required
def perfil_detail(request, pk=None):
    if pk is None:
        user_profile= request.user
        origen = "home"
    else:
        user_profile = get_object_or_404(Perfil, pk=pk)
        origen = "lista"

        if not request.user.is_superuser and user_profile != request.user:
            raise PermissionDenied

    return render(request, "users/perfil_detail.html", {"user_profile": user_profile, "origen": origen})

# Editar Perfil
@login_required
def perfil_change(request):
    if request.method == "POST":
        form = PerfilChangeForm(request.POST, request.FILES, instance = request.user)
        if form.is_valid():
            form.save()
            return redirect('perfil_detail')
    else:
        form = PerfilChangeForm(instance = request.user)
    
    return render(request, "users/perfil_change.html",{"form": form})

# Cambiar Passowrd
@login_required
def cambiar_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            # Importante: mantiene la sesión activa después de cambiar la contraseña
            update_session_auth_hash(request, user)
            messages.success(request, '¡Tu contraseña ha sido actualizada con éxito!')
            return redirect('perfil_detail') # Ajusta a tu URL de perfil
        else:
            messages.error(request, 'Por favor corrige los errores a continuación.')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, 'users/password_change.html', {'form': form})

# Confirmar Cierre de Sesión
@login_required
def confirmar_logout(request):
    return render(request, "users/logout.html", {"user": request.user})