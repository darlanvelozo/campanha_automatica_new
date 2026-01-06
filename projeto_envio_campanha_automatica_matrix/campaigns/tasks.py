"""
Tasks para execução de campanhas.
Pode ser usado com Celery ou executado diretamente.
"""

import threading
from .models import Campaign, Execution
from .services import CampaignAutomationService


def execute_campaign_sync(campaign_id: int) -> Execution:
    """
    Executa uma campanha de forma síncrona.
    
    Args:
        campaign_id: ID da campanha
    
    Returns:
        Instância de Execution criada
    """
    campaign = Campaign.objects.get(id=campaign_id)
    
    # Criar execução
    execution = Execution.objects.create(
        campaign=campaign,
        status='pending'
    )
    
    # Executar automação
    service = CampaignAutomationService(execution)
    service.execute()
    
    return execution


def execute_campaign_async(campaign_id: int):
    """
    Executa uma campanha de forma assíncrona usando threading.
    
    Args:
        campaign_id: ID da campanha
    """
    thread = threading.Thread(target=execute_campaign_sync, args=(campaign_id,))
    thread.daemon = True
    thread.start()


def execute_multiple_campaigns_async(campaign_ids: list):
    """
    Executa múltiplas campanhas de forma assíncrona.
    
    Args:
        campaign_ids: Lista de IDs de campanhas
    """
    for campaign_id in campaign_ids:
        execute_campaign_async(campaign_id)
