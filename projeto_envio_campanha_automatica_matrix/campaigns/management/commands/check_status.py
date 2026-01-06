"""
Management command para verificar o status do sistema.
"""

from django.core.management.base import BaseCommand
from campaigns.models import Campaign, Execution


class Command(BaseCommand):
    help = 'Verifica o status do sistema de campanhas'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('STATUS DO SISTEMA'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        # Verificar campanhas
        total_campaigns = Campaign.objects.count()
        active_campaigns = Campaign.objects.filter(enabled=True).count()
        
        self.stdout.write(f'\n📊 CAMPANHAS:')
        self.stdout.write(f'  Total: {total_campaigns}')
        self.stdout.write(f'  Ativas: {active_campaigns}')
        
        if total_campaigns > 0:
            self.stdout.write(f'\n📋 Primeiras 5 campanhas:')
            for campaign in Campaign.objects.all()[:5]:
                status = '✓ Ativa' if campaign.enabled else '✗ Inativa'
                self.stdout.write(f'  - ID {campaign.id}: {campaign.name} ({status})')
        else:
            self.stdout.write(self.style.WARNING('\n⚠️  NENHUMA CAMPANHA ENCONTRADA!'))
            self.stdout.write(self.style.WARNING('Execute: python3 manage.py import_campaigns'))
        
        # Verificar execuções
        total_executions = Execution.objects.count()
        self.stdout.write(f'\n🔄 EXECUÇÕES:')
        self.stdout.write(f'  Total: {total_executions}')
        
        if total_executions > 0:
            running = Execution.objects.filter(
                status__in=['pending', 'running', 'monitoring', 'creating_list', 'updating_campaign']
            ).count()
            completed = Execution.objects.filter(status='completed').count()
            failed = Execution.objects.filter(status='failed').count()
            
            self.stdout.write(f'  Em andamento: {running}')
            self.stdout.write(f'  Concluídas: {completed}')
            self.stdout.write(f'  Falhadas: {failed}')
        
        # URLs
        self.stdout.write(f'\n🌐 URLS DISPONÍVEIS:')
        self.stdout.write(f'  Dashboard: http://127.0.0.1:8000/')
        self.stdout.write(f'  Lista de Campanhas: http://127.0.0.1:8000/campaigns/')
        self.stdout.write(f'  Admin: http://127.0.0.1:8000/admin/')
        
        self.stdout.write(self.style.SUCCESS(f'\n{'='*60}'))
