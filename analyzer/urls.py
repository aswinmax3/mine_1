from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_policy, name='upload_policy'),
    path('policy/<int:pk>/', views.policy_dashboard, name='policy_dashboard'),
    path('policy/<int:pk>/chat/', views.policy_chat, name='policy_chat'),
    path('policy/<int:pk>/chat/ask/', views.chat_ask, name='chat_ask'),
    path('policy/<int:pk>/claim/', views.claim_check, name='claim_check'),
    path('policy/<int:pk>/negotiate/', views.negotiation_tips, name='negotiation_tips'),
    path('compare/', views.compare_view, name='compare'),
    path('recommend/', views.recommend_view, name='recommend'),
]

