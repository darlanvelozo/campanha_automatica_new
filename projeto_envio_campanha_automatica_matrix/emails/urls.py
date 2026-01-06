from django.urls import path
from . import views

app_name = 'emails'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_emails, name='dashboard'),
    
    # Campanhas de email
    path('campanhas/', views.listar_campanhas_email, name='listar_campanhas'),
    path('campanhas/nova/', views.criar_campanha_email, name='criar_campanha'),
    path('campanhas/<int:campanha_id>/', views.detalhe_campanha_email, name='detalhe_campanha'),
    path('campanhas/<int:campanha_id>/configurar/', views.configurar_campanha_email, name='configurar_campanha'),
    path('campanhas/<int:campanha_id>/executar/', views.executar_campanha_email, name='executar_campanha'),
    path('campanhas/<int:campanha_id>/pausar/', views.pausar_campanha_email, name='pausar_campanha'),
    path('campanhas/<int:campanha_id>/retomar/', views.retomar_campanha_email, name='retomar_campanha'),
    path('campanhas/<int:campanha_id>/cancelar/', views.cancelar_campanha_email, name='cancelar_campanha'),
    path('campanhas/<int:campanha_id>/status/', views.status_campanha_ajax, name='status_campanha_ajax'),
    path('campanhas/<int:campanha_id>/progresso/', views.progresso_campanha_ajax, name='progresso_campanha_ajax'),
    path('campanhas/<int:campanha_id>/processar-consulta/', views.processar_consulta_campanha, name='processar_consulta_campanha'),
    path('campanhas/<int:campanha_id>/exportar/', views.exportar_resultados_campanha, name='exportar_resultados'),
    
    # Templates de email
    path('templates/', views.listar_templates_email, name='listar_templates'),
    path('templates/<int:template_id>/visualizar/', views.visualizar_template_email, name='visualizar_template'),
    
    # Configurações SMTP
    path('config/<int:config_id>/testar/', views.testar_configuracao_smtp_ajax, name='testar_smtp'),
    
    # APIs AJAX para formulários
    path('api/template-sql/<int:template_id>/variaveis/', views.obter_variaveis_template_sql, name='obter_variaveis_template_sql'),
    
    # API para criar campanhas
    path('api/criar-campanha-execucao-unica/', views.api_criar_campanha_execucao_unica, name='api_criar_campanha_execucao_unica'),
    
    # APIs para consultar campanhas
    path('api/campanhas/', views.api_listar_campanhas, name='api_listar_campanhas'),
    path('api/campanhas/<int:campanha_id>/', views.api_detalhe_campanha, name='api_detalhe_campanha'),
    
    # APIs para consultar servidores de email
    path('api/servidores/', views.api_listar_servidores_email, name='api_listar_servidores_email'),
    path('api/servidores/<int:servidor_id>/', views.api_detalhe_servidor_email, name='api_detalhe_servidor_email'),
    
    # APIs para consultar templates de email
    path('api/templates/', views.api_listar_templates_email, name='api_listar_templates_email'),
    path('api/templates/<int:template_id>/', views.api_detalhe_template_email, name='api_detalhe_template_email'),
]
