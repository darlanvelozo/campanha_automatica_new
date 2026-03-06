from django.apps import AppConfig


class CampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'campaigns'
    verbose_name = 'Campanhas de Automação'
    
    def ready(self):
        import campaigns.signals  # Registrar signals