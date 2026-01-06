"""
URLs do app campaigns
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.CampaignListView.as_view(), name='campaign_list'),  # /campaigns/
    path('dashboard/', views.dashboard_view, name='dashboard'),  # /campaigns/dashboard/
    path('<int:pk>/', views.CampaignDetailView.as_view(), name='campaign_detail'),  # /campaigns/1/
    path('<int:campaign_id>/execute/', views.execute_campaign_view, name='execute_campaign'),  # /campaigns/1/execute/
    path('execute-multiple/', views.execute_multiple_campaigns_view, name='execute_multiple_campaigns'),  # /campaigns/execute-multiple/
    path('executions/<int:pk>/', views.ExecutionDetailView.as_view(), name='execution_detail'),  # /campaigns/executions/1/
    path('api/executions/<int:execution_id>/status/', views.execution_status_api, name='execution_status_api'),  # /campaigns/api/executions/1/status/
]
