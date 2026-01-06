"""
Management command para importar as 24 campanhas existentes do script original.
"""

from django.core.management.base import BaseCommand
from campaigns.models import Campaign


class Command(BaseCommand):
    help = 'Importa as 24 campanhas do script original para o banco de dados'
    
    def handle(self, *args, **options):
        # Campanhas Mega (12 campanhas)
        campanhas_mega = [
            {"name": "2 dias vencidos Mega", "campaign_id": 180, "dias": "2"},
            {"name": "3 dias vencidos Mega", "campaign_id": 169, "dias": "3"},
            {"name": "4 dias vencidos Mega", "campaign_id": 171, "dias": "4"},
            {"name": "8 dias vencidos Mega", "campaign_id": 173, "dias": "8"},
            {"name": "9 dias vencidos Mega", "campaign_id": 175, "dias": "9"},
            {"name": "20 dias vencidos Mega", "campaign_id": 76, "dias": "20"},
            {"name": "45 dias vencidos Mega", "campaign_id": 178, "dias": "45"},
            {"name": "60 dias vencidos Mega", "campaign_id": 182, "dias": "60"},
            {"name": "70 dias vencidos Mega", "campaign_id": 186, "dias": "70"},
            {"name": "75 dias vencidos Mega", "campaign_id": 187, "dias": "75"},
            {"name": "80 dias vencidos Mega", "campaign_id": 189, "dias": "80"},
            {"name": "90 dias vencidos Mega", "campaign_id": 191, "dias": "90"},
        ]
        
        # Campanhas BJ (12 campanhas)
        campanhas_bj = [
            {"name": "2 dias vencidos BJ", "campaign_id": 157, "dias": "2"},
            {"name": "3 dias vencidos BJ", "campaign_id": 170, "dias": "3"},
            {"name": "4 dias vencidos BJ", "campaign_id": 172, "dias": "4"},
            {"name": "8 dias vencidos BJ", "campaign_id": 174, "dias": "8"},
            {"name": "9 dias vencidos BJ", "campaign_id": 164, "dias": "9"},
            {"name": "20 dias vencidos BJ", "campaign_id": 176, "dias": "20"},
            {"name": "45 dias vencidos BJ", "campaign_id": 167, "dias": "45"},
            {"name": "60 dias vencidos BJ", "campaign_id": 184, "dias": "60"},
            {"name": "70 dias vencidos BJ", "campaign_id": 193, "dias": "70"},
            {"name": "75 dias vencidos BJ", "campaign_id": 188, "dias": "75"},
            {"name": "80 dias vencidos BJ", "campaign_id": 190, "dias": "80"},
            {"name": "90 dias vencidos BJ", "campaign_id": 192, "dias": "90"},
        ]
        
        total_criadas = 0
        total_atualizadas = 0
        
        # Importar campanhas Mega
        self.stdout.write(self.style.SUCCESS('Importando campanhas Mega...'))
        for campanha_data in campanhas_mega:
            campaign, created = Campaign.objects.update_or_create(
                campaign_id=campanha_data['campaign_id'],
                defaults={
                    'name': campanha_data['name'],
                    'description': f'Campanha automática para clientes com {campanha_data["dias"]} dias vencidos - Mega',
                    'template_sql_id': 3,
                    'credencial_banco_id': 1,
                    'credencial_hubsoft_id': 1,
                    'valores_variaveis': {
                        'dia1': campanha_data['dias'],
                        'dia2': campanha_data['dias']
                    },
                    'pular_consulta_api': False,
                    'enabled': True
                }
            )
            
            if created:
                total_criadas += 1
                self.stdout.write(f'  ✓ Criada: {campanha_data["name"]}')
            else:
                total_atualizadas += 1
                self.stdout.write(f'  ↻ Atualizada: {campanha_data["name"]}')
        
        # Importar campanhas BJ
        self.stdout.write(self.style.SUCCESS('\nImportando campanhas BJ...'))
        for campanha_data in campanhas_bj:
            campaign, created = Campaign.objects.update_or_create(
                campaign_id=campanha_data['campaign_id'],
                defaults={
                    'name': campanha_data['name'],
                    'description': f'Campanha automática para clientes com {campanha_data["dias"]} dias vencidos - BJ',
                    'template_sql_id': 4,
                    'credencial_banco_id': 2,
                    'credencial_hubsoft_id': 2,
                    'valores_variaveis': {
                        'dia1': campanha_data['dias'],
                        'dia2': campanha_data['dias']
                    },
                    'pular_consulta_api': False,
                    'enabled': True
                }
            )
            
            if created:
                total_criadas += 1
                self.stdout.write(f'  ✓ Criada: {campanha_data["name"]}')
            else:
                total_atualizadas += 1
                self.stdout.write(f'  ↻ Atualizada: {campanha_data["name"]}')
        
        # Resumo
        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS(f'IMPORTAÇÃO CONCLUÍDA'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}'))
        self.stdout.write(f'Total de campanhas criadas: {total_criadas}')
        self.stdout.write(f'Total de campanhas atualizadas: {total_atualizadas}')
        self.stdout.write(f'Total: {total_criadas + total_atualizadas}')
