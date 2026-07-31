from django.urls import path
from main.views import *

urlpatterns = [
    path("",home, name="home"),
    path("kiosco-familia", kiosco_familia, name="kiosco_familia"),
    path("comedor-familia", comedor_familia, name="comedor_familia"),
    path("resultado_importacion", resultado_importacion, name="resultado_importacion"),
    path('verificar-otp/', verificacion_otp, name='verificar_otp'),
]