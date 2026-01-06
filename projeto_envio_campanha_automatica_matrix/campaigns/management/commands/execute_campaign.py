"""
Management command para executar uma ou mais campanhas via CLI.
"""

from django.core.management.base import BaseCommand
from campaigns.models import Campaign
from campaigns.tasks import execute_campaign_sync


class Command(BaseCommand):
    help = 'Executa uma ou mais campanhas'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--campaign-id',
            type=int,
            help='ID da campanha para executar'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Executar todas as campanhas ativas'
        )
        parser.add_argument(
            '--name',
            type=str,
            help='Nome da campanha (busca parcial)'
        )
    
    def handle(self, *args, **options):
        campaign_id = options.get('campaign_id')
        execute_all = options.get('all')
        name = options.get('name')
        
        if not any([campaign_id, execute_all, name]):
            self.stdout.write(self.style.ERROR('Você deve especificar --campaign-id, --name ou --all'))
            return
        
        campaigns = []
        
        if campaign_id:
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                campaigns = [campaign]
            except Campaign.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Campanha com ID {campaign_id} não encontrada'))
                return
        
        elif name:
            campaigns = Campaign.objects.filter(name__icontains=name, enabled=True)
            if not campaigns.exists():
                self.stdout.write(self.style.ERROR(f'Nenhuma campanha ativa encontrada com nome "{name}"'))
                return
        
        elif execute_all:
            campaigns = Campaign.objects.filter(enabled=True)
            if not campaigns.exists():
                self.stdout.write(self.style.ERROR('Nenhuma campanha ativa encontrada'))
                return
        
        self.stdout.write(self.style.SUCCESS(f'Executando {campaigns.count()} campanha(s)...'))
        
        for campaign in campaigns:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Executando: {campaign.name}')
            self.stdout.write(f'{"="*60}')
            
            try:
                execution = execute_campaign_sync(campaign.id)
                
                if execution.success:
                    self.stdout.write(self.style.SUCCESS(f'✓ Sucesso! Execução ID: {execution.id}'))
                    self.stdout.write(f'  - Total de registros: {execution.total_records}')
                    self.stdout.write(f'  - Lista ID: {execution.lista_id}')
                else:
                    self.stdout.write(self.style.ERROR(f'✗ Falhou! Execução ID: {execution.id}'))
                    if execution.error_message:
                        self.stdout.write(f'  - Erro: {execution.error_message}')
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Erro ao executar: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('EXECUÇÃO CONCLUÍDA'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}'))
