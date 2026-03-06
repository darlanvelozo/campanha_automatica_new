"""
Configuração do app campanha_manager
"""
from django.apps import AppConfig


class CampanhaManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'campanha_manager'
    verbose_name = 'Gerenciador de Campanhas'
