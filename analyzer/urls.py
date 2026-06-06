from django.urls import path
from . import views

urlpatterns = [

    path('', views.enter_project, name='enter_project'),

    path('dashboard/', views.dashboard, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    path('upload/', views.upload_policy, name='upload_policy'),

    path('policy/<int:pk>/', views.policy_dashboard, name='policy_dashboard'),
    path('policy/<int:pk>/download-pdf/', views.download_policy_pdf, name='download_policy_pdf'),
    path('policy/<int:pk>/chat/', views.policy_chat, name='policy_chat'),
    path('policy/<int:pk>/chat/ask/', views.chat_ask, name='chat_ask'),
    path('policy/<int:pk>/delete/', views.delete_policy, name='delete_policy'),
    path('policy/<int:pk>/claim/', views.claim_check, name='claim_check'),
    path('policy/<int:pk>/negotiate/', views.negotiation_tips, name='negotiation_tips'),
    path('policy/<int:pk>/complaint/', views.complaint_letter, name='complaint_letter'),
    path('policy/<int:pk>/set-expiry/', views.set_expiry, name='set_expiry'),

    path('compare/', views.compare_view, name='compare'),
    path('recommend/', views.recommend_view, name='recommend'),
    path('coverage-gap/', views.coverage_gap, name='coverage_gap'),

    path('chat/all/', views.multi_policy_chat, name='multi_policy_chat'),
    path('chat/all/ask/', views.multi_policy_ask, name='multi_policy_ask'),

    path('premium-calculator/', views.premium_calculator, name='premium_calculator'),
    path('profile/', views.profile_view, name='profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='index'),
    path('robot/', views.enter_project, name='enter_project'),
]