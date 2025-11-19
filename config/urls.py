from django.contrib import admin
from django.urls import path
from main import views  # Импорт views из приложения main

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),  # Главная страница
]