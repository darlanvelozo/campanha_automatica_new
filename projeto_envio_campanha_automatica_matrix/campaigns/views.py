"""
Views para o sistema de campanhas.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import ListView, DetailView
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .models import Campaign, Execution, ExecutionLog
from .tasks import execute_campaign_async, execute_multiple_campaigns_async


class CampaignListView(ListView):
    """Lista todas as campanhas"""
    model = Campaign
    template_name = 'campaigns/campaign_list.html'
    context_object_name = 'campaigns'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = Campaign.objects.all()
        
        # Filtro por status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(enabled=True)
        elif status == 'inactive':
            queryset = queryset.filter(enabled=False)
        
        # Busca
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset.order_by('name')


class CampaignDetailView(DetailView):
    """Detalhes de uma campanha"""
    model = Campaign
    template_name = 'campaigns/campaign_detail.html'
    context_object_name = 'campaign'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['executions'] = self.object.executions.all()[:10]
        return context


class ExecutionDetailView(DetailView):
    """Detalhes de uma execução"""
    model = Execution
    template_name = 'campaigns/execution_detail.html'
    context_object_name = 'execution'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['logs'] = self.object.logs.all()
        return context


@require_POST
def execute_campaign_view(request, campaign_id):
    """Executa uma campanha"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    if not campaign.enabled:
        messages.error(request, f'A campanha "{campaign.name}" está desativada!')
        return redirect('campaign_list')
    
    # Verificar se já existe execução em andamento
    if campaign.has_running_execution():
        messages.warning(
            request, 
            f'A campanha "{campaign.name}" já possui uma execução em andamento. '
            'Aguarde a finalização antes de executar novamente.'
        )
        return redirect('campaign_detail', pk=campaign_id)
    
    # Executar de forma assíncrona
    execute_campaign_async(campaign_id)
    
    messages.success(request, f'Campanha "{campaign.name}" iniciada com sucesso!')
    return redirect('campaign_detail', pk=campaign_id)


@require_POST
def execute_multiple_campaigns_view(request):
    """Executa múltiplas campanhas"""
    campaign_ids = request.POST.getlist('campaign_ids')
    
    if not campaign_ids:
        messages.error(request, 'Nenhuma campanha selecionada!')
        return redirect('campaign_list')
    
    # Filtrar apenas campanhas ativas
    campaigns = Campaign.objects.filter(id__in=campaign_ids, enabled=True)
    
    if not campaigns.exists():
        messages.error(request, 'Nenhuma campanha ativa selecionada!')
        return redirect('campaign_list')
    
    # Filtrar campanhas que NÃO estão em execução
    campaigns_to_execute = []
    campaigns_already_running = []
    
    for campaign in campaigns:
        if campaign.has_running_execution():
            campaigns_already_running.append(campaign.name)
        else:
            campaigns_to_execute.append(campaign)
    
    # Avisar sobre campanhas que já estão executando
    if campaigns_already_running:
        messages.warning(
            request,
            f'As seguintes campanhas já estão em execução e foram ignoradas: '
            f'{", ".join(campaigns_already_running)}'
        )
    
    # Executar campanhas disponíveis
    if campaigns_to_execute:
        execute_multiple_campaigns_async([c.id for c in campaigns_to_execute])
        messages.success(
            request, 
            f'{len(campaigns_to_execute)} campanha(s) iniciada(s) com sucesso!'
        )
    else:
        messages.info(request, 'Todas as campanhas selecionadas já estão em execução.')
    
    return redirect('campaign_list')


def execution_status_api(request, execution_id):
    """API para obter status de uma execução em tempo real"""
    execution = get_object_or_404(Execution, id=execution_id)
    
    data = {
        'id': execution.id,
        'campaign_name': execution.campaign.name,
        'status': execution.status,
        'status_display': execution.get_status_display(),
        'success': execution.success,
        'total_records': execution.total_records,
        'execucao_id': execution.execucao_id,
        'lista_id': execution.lista_id,
        'error_message': execution.error_message,
        'started_at': execution.started_at.isoformat() if execution.started_at else None,
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'duration': execution.duration_str(),
        'logs': [
            {
                'timestamp': log.timestamp.isoformat(),
                'level': log.level,
                'message': log.message
            }
            for log in execution.logs.all()[:50]  # Últimos 50 logs
        ]
    }
    
    return JsonResponse(data)


def dashboard_view(request):
    """Dashboard com visão geral"""
    total_campaigns = Campaign.objects.count()
    active_campaigns = Campaign.objects.filter(enabled=True).count()
    recent_executions = Execution.objects.all()[:10]
    running_executions = Execution.objects.filter(
        status__in=['pending', 'running', 'monitoring', 'creating_list', 'updating_campaign']
    )
    
    context = {
        'total_campaigns': total_campaigns,
        'active_campaigns': active_campaigns,
        'recent_executions': recent_executions,
        'running_executions': running_executions,
    }
    
    return render(request, 'campaigns/dashboard.html', context)
