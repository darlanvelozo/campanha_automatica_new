"""
Views principais do sistema - Dashboard Geral e views compartilhadas
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.http import require_http_methods
from datetime import timedelta, datetime

# Importar models dos apps
try:
    from campanhas.models import EnvioHSMMatrix, EnvioHSMIndividual
except ImportError as e:
    print(f"IMPORT ERROR campanhas: {e}")
    EnvioHSMMatrix = None
    EnvioHSMIndividual = None

try:
    from emails.models import CampanhaEmail, EnvioEmailIndividual
except ImportError:
    CampanhaEmail = None
    EnvioEmailIndividual = None

try:
    from campaigns.models import Campaign, Execution
except ImportError:
    Campaign = None
    Execution = None


def dashboard_geral(request):
    """Dashboard unificado mostrando todas as áreas"""
    
    # Processar filtros de data
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    
    # Filtro padrão: últimos 30 dias
    if data_fim_str:
        try:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            data_fim = timezone.make_aware(data_fim) if timezone.is_naive(data_fim) else data_fim
        except (ValueError, TypeError) as e:
            print(f"Erro ao processar data_fim: {e}")
            data_fim = timezone.now()
    else:
        data_fim = timezone.now()
    
    if data_inicio_str:
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            data_inicio = timezone.make_aware(data_inicio) if timezone.is_naive(data_inicio) else data_inicio
        except (ValueError, TypeError) as e:
            print(f"Erro ao processar data_inicio: {e}")
            data_inicio = data_fim - timedelta(days=30)
    else:
        data_inicio = data_fim - timedelta(days=30)
    
    # Estatísticas WhatsApp/HSM com métricas detalhadas
    stats_whatsapp = {}
    try:
        if EnvioHSMIndividual is not None:
            # Filtrar por envio_matrix__data_criacao se data_envio for null
            # Buscar todos os envios individuais relacionados a envios matrix criados no período
            envios_periodo = EnvioHSMIndividual.objects.filter(
                Q(data_envio__gte=data_inicio, data_envio__lte=data_fim) |
                Q(data_envio__isnull=True, envio_matrix__data_criacao__gte=data_inicio, envio_matrix__data_criacao__lte=data_fim)
            )
            
            total = envios_periodo.count()
            enviados = envios_periodo.filter(status='enviado').count()
            erros = envios_periodo.filter(status='erro').count()
            pendentes = envios_periodo.filter(status__in=['pendente', 'enviando']).count()
            cancelados = envios_periodo.filter(status='cancelado').count()
            
            taxa_sucesso = (enviados / total * 100) if total > 0 else 0
            
            stats_whatsapp = {
                'total_envios': total,
                'enviados': enviados,
                'erros': erros,
                'pendentes': pendentes,
                'cancelados': cancelados,
                'taxa_sucesso': round(taxa_sucesso, 1),
                'envios_hoje': EnvioHSMIndividual.objects.filter(
                    Q(data_envio__date=timezone.now().date()) |
                    Q(data_envio__isnull=True, envio_matrix__data_criacao__date=timezone.now().date())
                ).count() if EnvioHSMIndividual else 0,
            }
    except Exception as e:
        print(f"Erro ao obter stats WhatsApp: {e}")
        import traceback
        traceback.print_exc()
        stats_whatsapp = {'total_envios': 0, 'enviados': 0, 'erros': 0, 'pendentes': 0, 'cancelados': 0, 'taxa_sucesso': 0}
    
    # Estatísticas Emails com métricas detalhadas
    stats_emails = {}
    try:
        if EnvioEmailIndividual:
            # Total no período
            envios_periodo = EnvioEmailIndividual.objects.filter(
                data_envio__gte=data_inicio,
                data_envio__lte=data_fim
            )
            
            total = envios_periodo.count()
            enviados = envios_periodo.filter(status='enviado').count()
            erros = envios_periodo.filter(status='erro').count()
            pendentes = envios_periodo.filter(status__in=['pendente', 'enviando']).count()
            
            taxa_sucesso = (enviados / total * 100) if total > 0 else 0
            
            stats_emails = {
                'total_campanhas': CampanhaEmail.objects.count() if CampanhaEmail else 0,
                'total_envios': total,
                'enviados': enviados,
                'erros': erros,
                'pendentes': pendentes,
                'taxa_sucesso': round(taxa_sucesso, 1),
            }
    except Exception as e:
        print(f"Erro ao obter stats Emails: {e}")
        stats_emails = {'total_envios': 0, 'enviados': 0, 'erros': 0, 'pendentes': 0, 'taxa_sucesso': 0}
    
    # Estatísticas Native (Execuções e Ligações)
    stats_native = {}
    try:
        if Execution:
            # Execuções no período
            execucoes_periodo = Execution.objects.filter(
                started_at__gte=data_inicio,
                started_at__lte=data_fim
            )
            
            total_execucoes = execucoes_periodo.count()
            concluidas = execucoes_periodo.filter(status='completed').count()
            falhas = execucoes_periodo.filter(status='failed').count()
            
            # Total de registros processados (ligações geradas)
            total_registros = sum(e.total_records or 0 for e in execucoes_periodo)
            
            stats_native = {
                'total_campanhas': Campaign.objects.count() if Campaign else 0,
                'total_execucoes': total_execucoes,
                'execucoes_concluidas': concluidas,
                'execucoes_falhas': falhas,
                'total_ligacoes': total_registros,
                'campanhas_ativas': Campaign.objects.filter(enabled=True).count() if Campaign else 0,
            }
    except Exception as e:
        print(f"Erro ao obter stats Native: {e}")
        stats_native = {'total_execucoes': 0, 'execucoes_concluidas': 0, 'execucoes_falhas': 0, 'total_ligacoes': 0}
    
    # Atividades recentes (últimas 10)
    atividades = []
    
    # Adicionar envios HSM recentes
    try:
        if EnvioHSMMatrix:
            envios_hsm = EnvioHSMMatrix.objects.all().order_by('-id')[:5]
            for envio in envios_hsm:
                atividades.append({
                    'tipo': 'whatsapp',
                    'icone': 'message-circle',
                    'titulo': str(envio.titulo) if hasattr(envio, 'titulo') and envio.titulo else f'Envio HSM #{envio.id}',
                    'data': envio.data_criacao if hasattr(envio, 'data_criacao') else timezone.now(),
                    'url': f'/whatsapp/envio-hsm/{envio.id}/',
                })
    except Exception as e:
        print(f"Erro ao obter envios HSM: {e}")
    
    # Adicionar campanhas de email recentes
    try:
        if CampanhaEmail:
            campanhas_email = CampanhaEmail.objects.all().order_by('-id')[:5]
            for campanha in campanhas_email:
                atividades.append({
                    'tipo': 'email',
                    'icone': 'mail',
                    'titulo': campanha.nome,
                    'data': campanha.data_criacao if hasattr(campanha, 'data_criacao') else timezone.now(),
                    'url': f'/emails/campanhas/{campanha.id}/',
                })
    except Exception as e:
        print(f"Erro ao obter campanhas email: {e}")
    
    # Ordenar atividades por data
    if atividades:
        atividades.sort(key=lambda x: x['data'], reverse=True)
        atividades = atividades[:10]  # Limitar a 10
    
    context = {
        'stats_whatsapp': stats_whatsapp,
        'stats_emails': stats_emails,
        'stats_native': stats_native,
        'atividades': atividades,
        'data_inicio': data_inicio.strftime('%Y-%m-%d') if data_inicio else '',
        'data_fim': data_fim.strftime('%Y-%m-%d') if data_fim else '',
        'periodo_selecionado': f"{data_inicio.strftime('%d/%m/%Y')} - {data_fim.strftime('%d/%m/%Y')}",
    }
    
    return render(request, 'dashboard_geral.html', context)


def busca_global(request):
    """API de busca global unificada"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({
            'campanhas_email': [],
            'envios_hsm': [],
            'campanhas_native': [],
        })
    
    resultados = {}
    
    # Buscar campanhas de email
    if CampanhaEmail:
        campanhas_email = CampanhaEmail.objects.filter(
            nome__icontains=query
        )[:5]
        resultados['campanhas_email'] = [
            {'id': c.id, 'nome': c.nome}
            for c in campanhas_email
        ]
    else:
        resultados['campanhas_email'] = []
    
    # Buscar envios HSM
    if EnvioHSMMatrix:
        envios_hsm = EnvioHSMMatrix.objects.filter(
            Q(titulo__icontains=query) | Q(id__icontains=query)
        )[:5]
        resultados['envios_hsm'] = [
            {'id': e.id, 'titulo': e.titulo or f'Envio #{e.id}'}
            for e in envios_hsm
        ]
    else:
        resultados['envios_hsm'] = []
    
    # Buscar campanhas native
    if Campaign:
        campanhas_native = Campaign.objects.filter(
            name__icontains=query
        )[:5]
        resultados['campanhas_native'] = [
            {'id': c.id, 'name': c.name}
            for c in campanhas_native
        ]
    else:
        resultados['campanhas_native'] = []
    
    return JsonResponse(resultados)


def notificacoes_api(request):
    """API de notificações - retorna notificações do usuário"""
    from .services import ServicoNotificacao
    
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)
    
    # Parâmetros
    apenas_nao_lidas = request.GET.get('apenas_nao_lidas', 'true').lower() == 'true'
    limite = int(request.GET.get('limite', 50))
    
    # Buscar notificações
    notificacoes = ServicoNotificacao.obter_notificacoes_usuario(
        usuario=request.user,
        apenas_nao_lidas=apenas_nao_lidas,
        limite=limite
    )
    
    # Serializar
    dados = []
    for notif in notificacoes:
        dados.append({
            'id': notif.id,
            'tipo': notif.tipo_notificacao.codigo if notif.tipo_notificacao else 'sistema',
            'categoria': notif.tipo_notificacao.categoria if notif.tipo_notificacao else 'sistema',
            'titulo': notif.titulo,
            'mensagem': notif.mensagem,
            'icone': notif.icone,
            'cor': notif.cor,
            'url': notif.url,
            'lida': notif.lida,
            'data_criacao': notif.data_criacao.isoformat(),
            'data_leitura': notif.data_leitura.isoformat() if notif.data_leitura else None,
            'tempo_relativo': notif.tempo_relativo,
        })
    
    return JsonResponse(dados, safe=False)


def marcar_notificacao_lida(request, notificacao_id):
    """Marca uma notificação como lida"""
    from .services import ServicoNotificacao
    from .models import Notificacao
    
    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Não autenticado'}, status=401)
    
    try:
        notificacao = Notificacao.objects.get(id=notificacao_id, usuario=request.user)
        notificacao.marcar_como_lida()
        return JsonResponse({'sucesso': True})
    except Notificacao.DoesNotExist:
        return JsonResponse({'erro': 'Notificação não encontrada'}, status=404)


def marcar_todas_notificacoes_lidas(request):
    """Marca todas as notificações como lidas"""
    from .services import ServicoNotificacao
    
    if not request.user.is_authenticated:
        return JsonResponse({'erro': 'Não autenticado'}, status=401)
    
    ServicoNotificacao.marcar_todas_como_lidas(request.user)
    return JsonResponse({'sucesso': True})


def configuracoes_notificacoes(request):
    """Página de configurações de notificações do usuário"""
    from .models import TipoNotificacao, ConfiguracaoNotificacao
    from django.contrib.auth.decorators import login_required
    
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    # Buscar todos os tipos de notificação
    tipos_notificacao = TipoNotificacao.objects.filter(ativo=True).order_by('categoria', 'nome')
    
    # Organizar por categoria
    tipos_por_categoria = {}
    for tipo in tipos_notificacao:
        categoria = tipo.get_categoria_display()
        if categoria not in tipos_por_categoria:
            tipos_por_categoria[categoria] = []
        
        # Buscar configuração do usuário
        config = ConfiguracaoNotificacao.objects.filter(
            usuario=request.user,
            tipo_notificacao=tipo
        ).first()
        
        tipos_por_categoria[categoria].append({
            'tipo': tipo,
            'config': config,
            'ativo': config.ativo if config else True,  # Ativo por padrão
            'enviar_email': config.enviar_email if config else False
        })
    
    # Processar formulário
    if request.method == 'POST':
        for tipo in tipos_notificacao:
            ativo = request.POST.get(f'notif_{tipo.id}') == 'on'
            enviar_email = request.POST.get(f'email_{tipo.id}') == 'on'
            
            config, created = ConfiguracaoNotificacao.objects.get_or_create(
                usuario=request.user,
                tipo_notificacao=tipo,
                defaults={'ativo': ativo, 'enviar_email': enviar_email}
            )
            
            if not created:
                config.ativo = ativo
                config.enviar_email = enviar_email
                config.save()
        
        from django.contrib import messages
        messages.success(request, 'Configurações de notificações salvas com sucesso!')
        return redirect('configuracoes_notificacoes')
    
    context = {
        'tipos_por_categoria': tipos_por_categoria,
    }
    
    return render(request, 'configuracoes_notificacoes.html', context)


@require_http_methods(["POST"])
def deletar_notificacao(request, pk):
    """Deleta uma notificação específica"""
    from .models import Notificacao
    
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Não autenticado'}, status=401)
    
    notificacao = get_object_or_404(Notificacao, id=pk, usuario=request.user)
    notificacao.delete()
    
    return JsonResponse({'status': 'success', 'message': 'Notificação removida'})


@require_http_methods(["POST"])
def limpar_todas_notificacoes(request):
    """Limpa/deleta todas as notificações do usuário"""
    from .models import Notificacao
    
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Não autenticado'}, status=401)
    
    # Deletar todas as notificações do usuário
    count = Notificacao.objects.filter(usuario=request.user).delete()[0]
    
    return JsonResponse({
        'status': 'success', 
        'message': f'{count} notificações removidas'
    })


def dashboard_metrics_api(request):
    """API para retornar métricas do dashboard em formato JSON para gráficos"""
    
    # Processar filtros de data
    data_inicio_str = request.GET.get('data_inicio')
    data_fim_str = request.GET.get('data_fim')
    
    # Filtro padrão: últimos 30 dias
    if data_fim_str:
        try:
            data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            data_fim = timezone.make_aware(data_fim) if timezone.is_naive(data_fim) else data_fim
        except (ValueError, TypeError):
            data_fim = timezone.now()
    else:
        data_fim = timezone.now()
    
    if data_inicio_str:
        try:
            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0)
            data_inicio = timezone.make_aware(data_inicio) if timezone.is_naive(data_inicio) else data_inicio
        except (ValueError, TypeError):
            data_inicio = data_fim - timedelta(days=30)
    else:
        data_inicio = data_fim - timedelta(days=30)
    
    metrics = {
        'hsm': {'total': 0, 'enviados': 0, 'erros': 0, 'pendentes': 0, 'taxa_sucesso': 0},
        'email': {'total': 0, 'enviados': 0, 'erros': 0, 'pendentes': 0, 'taxa_sucesso': 0},
        'native': {'total_execucoes': 0, 'concluidas': 0, 'falhas': 0, 'total_ligacoes': 0},
    }
    
    # Métricas HSM
    try:
        if EnvioHSMIndividual:
            envios_periodo = EnvioHSMIndividual.objects.filter(
                Q(data_envio__gte=data_inicio, data_envio__lte=data_fim) |
                Q(data_envio__isnull=True, envio_matrix__data_criacao__gte=data_inicio, envio_matrix__data_criacao__lte=data_fim)
            )
            
            total = envios_periodo.count()
            enviados = envios_periodo.filter(status='enviado').count()
            erros = envios_periodo.filter(status='erro').count()
            pendentes = envios_periodo.filter(status__in=['pendente', 'enviando']).count()
            
            metrics['hsm'] = {
                'total': total,
                'enviados': enviados,
                'erros': erros,
                'pendentes': pendentes,
                'taxa_sucesso': round((enviados / total * 100), 1) if total > 0 else 0
            }
    except Exception as e:
        print(f"Erro ao obter métricas HSM: {e}")
    
    # Métricas Email
    try:
        if EnvioEmailIndividual:
            envios_periodo = EnvioEmailIndividual.objects.filter(
                data_envio__gte=data_inicio,
                data_envio__lte=data_fim
            )
            
            total = envios_periodo.count()
            enviados = envios_periodo.filter(status='enviado').count()
            erros = envios_periodo.filter(status='erro').count()
            pendentes = envios_periodo.filter(status__in=['pendente', 'enviando']).count()
            
            metrics['email'] = {
                'total': total,
                'enviados': enviados,
                'erros': erros,
                'pendentes': pendentes,
                'taxa_sucesso': round((enviados / total * 100), 1) if total > 0 else 0
            }
    except Exception as e:
        print(f"Erro ao obter métricas Email: {e}")
    
    # Métricas Native
    try:
        if Execution:
            execucoes_periodo = Execution.objects.filter(
                started_at__gte=data_inicio,
                started_at__lte=data_fim
            )
            
            total_execucoes = execucoes_periodo.count()
            concluidas = execucoes_periodo.filter(status='completed').count()
            falhas = execucoes_periodo.filter(status='failed').count()
            total_registros = sum(e.total_records or 0 for e in execucoes_periodo)
            
            metrics['native'] = {
                'total_execucoes': total_execucoes,
                'concluidas': concluidas,
                'falhas': falhas,
                'total_ligacoes': total_registros,
            }
    except Exception as e:
        print(f"Erro ao obter métricas Native: {e}")
    
    return JsonResponse(metrics)


def test_design_system(request):
    """View temporária para testar o design system"""
    return render(request, 'test_design_system.html')
