"""
Comando para inicializar tipos de notificações do sistema
"""
from django.core.management.base import BaseCommand
from campanha_manager.services import ServicoNotificacao


class Command(BaseCommand):
    help = 'Inicializa os tipos de notificações padrão do sistema'
    
    def handle(self, *args, **options):
        self.stdout.write('Inicializando tipos de notificações...')
        
        criados = ServicoNotificacao.inicializar_tipos_notificacao()
        
        if criados > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ {criados} tipos de notificação criados com sucesso!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Todos os tipos de notificação já existem.')
            )
