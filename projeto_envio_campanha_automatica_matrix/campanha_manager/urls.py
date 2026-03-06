"""
URL configuration for campanha_manager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views as main_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Dashboard geral como página inicial
    path('', main_views.dashboard_geral, name='dashboard_geral'),
    
    # Configurações
    path('configuracoes/notificacoes/', main_views.configuracoes_notificacoes, name='configuracoes_notificacoes'),
    
    # Busca global
    path('api/busca-global/', main_views.busca_global, name='busca_global'),
    
    # Dashboard Metrics API
    path('api/dashboard-metrics/', main_views.dashboard_metrics_api, name='dashboard_metrics_api'),
    
    # Notificações
    path('api/notificacoes/', main_views.notificacoes_api, name='notificacoes_api'),
    path('api/notificacoes/<int:pk>/deletar/', main_views.deletar_notificacao, name='deletar_notificacao'),
    path('api/notificacoes/<int:notificacao_id>/marcar-lida/', main_views.marcar_notificacao_lida, name='marcar_notificacao_lida'),
    path('api/notificacoes/marcar-todas-lidas/', main_views.marcar_todas_notificacoes_lidas, name='marcar_todas_notificacoes_lidas'),
    path('api/notificacoes/limpar-todas/', main_views.limpar_todas_notificacoes, name='limpar_todas_notificacoes'),
    
    # Página de teste (temporária - remover em produção)
    path('test-design/', main_views.test_design_system, name='test_design_system'),
    
    # Módulos (com namespaces)
    path('whatsapp/', include('campanhas.urls')),
    path('emails/', include('emails.urls')),
    path('native/', include('campaigns.urls')),
    
    # APIs
    path('api/', include('campanhas.api_urls')),
    path('api-auth/', include('rest_framework.urls')),  # URLs para login/logout da API
]

# Servir arquivos estáticos em desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
