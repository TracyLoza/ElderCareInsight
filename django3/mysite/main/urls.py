from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('home/', views.home, name='home'),
    path('patient/', views.patient, name='patient'),
    path('patient_list/', views.patient_list, name='patient_list'),
    path('settings/', views.settings, name='settings'),
    path('about/', views.about, name='about'),
    path('boot/', views.boot, name='boot'),
]