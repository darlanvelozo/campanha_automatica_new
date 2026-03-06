from django.apps import AppConfig


class CampanhasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'campanhas'
    
    def ready(self):
        import campanhas.signals  # Registrar signals