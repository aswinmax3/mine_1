from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('upload/', views.upload_document, name='upload_document'),
    path('result/<int:pk>/', views.result, name='result'),
    path('recommendations/', views.recommendations, name='recommendations'),

    path('register/', views.register, name='register'),

    path(
        'login/',
        auth_views.LoginView.as_view(template_name='analyzer/login.html'),
        name='login'
    ),

    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout'
    ),
]