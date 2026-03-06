from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q, Count
import json
from datetime import datetime, timedelta
from .models import (
    ConfiguracaoServidorEmail, TemplateEmail, CampanhaEmail, 
    EnvioEmailIndividual, LogEnvioEmail, BaseLeads, Lead
)
from .services_csv import ServicoImportacaoCSV
from .services import (
    GerenciadorCampanhaEmail, testar_configuracao_smtp, 
    obter_estatisticas_campanha
)
from campanhas.models import TemplateSQL, ConsultaExecucao, CredenciaisBancoDados, CredenciaisHubsoft
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


def dashboard_emails(request):
    """Dashboard principal do sistema de emails"""
    
    # Estatísticas gerais
    stats = {
        'total_campanhas': CampanhaEmail.objects.count(),
        'campanhas_ativas': CampanhaEmail.objects.filter(ativo=True).count(),
        'campanhas_executando': CampanhaEmail.objects.filter(status='executando').count(),
        'campanhas_agendadas': CampanhaEmail.objects.filter(status='agendada').count(),
        'total_templates': TemplateEmail.objects.count(),
        'templates_ativos': TemplateEmail.objects.filter(ativo=True).count(),
        'total_configuracoes': ConfiguracaoServidorEmail.objects.count(),
        'configuracoes_ativas': ConfiguracaoServidorEmail.objects.filter(ativo=True).count(),
    }
    
    # Campanhas recentes
    campanhas_recentes = CampanhaEmail.objects.select_related(
        'template_email', 'configuracao_servidor'
    ).order_by('-data_criacao')[:5]
    
    # Estatísticas de envio (últimos 30 dias)
    desde = timezone.now() - timedelta(days=30)
    
    envios_mes = EnvioEmailIndividual.objects.filter(
        data_envio__gte=desde
    ).count()
    
    sucessos_mes = EnvioEmailIndividual.objects.filter(
        data_envio__gte=desde,
        status='enviado'
    ).count()
    
    taxa_sucesso_mes = (sucessos_mes / envios_mes * 100) if envios_mes > 0 else 0
    
    # Logs recentes
    logs_recentes = LogEnvioEmail.objects.order_by('-data_criacao')[:10]
    
    # Templates mais usados
    templates_populares = TemplateEmail.objects.filter(
        total_enviados__gt=0
    ).order_by('-total_enviados')[:5]
    
    # Bases de leads recentes
    try:
        bases_leads = BaseLeads.objects.order_by('-data_importacao')[:5]
    except Exception as e:
        logger.error(f"Erro ao buscar bases de leads: {e}")
        bases_leads = []
    
    # Estatísticas por status
    from django.db.models import Count
    try:
        stats_por_status = list(CampanhaEmail.objects.values('status').annotate(
            total=Count('id')
        ).order_by('-total'))
        
        # Adicionar display name para cada status
        status_dict = dict(CampanhaEmail.STATUS_CHOICES)
        for stat in stats_por_status:
            stat['status_display'] = status_dict.get(stat['status'], stat['status'])
    except Exception as e:
        logger.error(f"Erro ao gerar estatísticas por status: {e}")
        stats_por_status = []
    
    # Adicionar emails_enviados ao stats
    stats['emails_enviados'] = envios_mes
    
    context = {
        'stats': stats,
        'campanhas_recentes': campanhas_recentes,
        'envios_mes': envios_mes,
        'sucessos_mes': sucessos_mes,
        'taxa_sucesso_mes': taxa_sucesso_mes,
        'logs_recentes': logs_recentes,
        'templates_populares': templates_populares,
        'bases_leads': bases_leads,
        'stats_por_status': stats_por_status,
    }
    
    return render(request, 'emails/dashboard.html', context)


def listar_campanhas_email(request):
    """Lista todas as campanhas de email"""
    
    # Filtros
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    # Query base
    campanhas = CampanhaEmail.objects.all().select_related(
        'template_email', 'configuracao_servidor', 'template_sql'
    )
    
    # Aplicar filtros
    if status_filter:
        campanhas = campanhas.filter(status=status_filter)
    
    if search:
        campanhas = campanhas.filter(
            Q(nome__icontains=search) |
            Q(descricao__icontains=search) |
            Q(template_email__nome__icontains=search)
        )
    
    # Ordenação
    campanhas = campanhas.order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(campanhas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas gerais
    stats = {
        'total_campanhas': CampanhaEmail.objects.count(),
        'ativas': CampanhaEmail.objects.filter(ativo=True).count(),
        'executando': CampanhaEmail.objects.filter(status='executando').count(),
        'agendadas': CampanhaEmail.objects.filter(status='agendada').count(),
    }
    
    context = {
        'page_obj': page_obj,
        'campanhas': page_obj,  # Alias para compatibilidade
        'has_executing': CampanhaEmail.objects.filter(status='executando').exists(),
        'stats': stats,
        'status_filter': status_filter,
        'search': search,
        'status_choices': CampanhaEmail.STATUS_CHOICES,
    }
    
    return render(request, 'emails/listar_campanhas.html', context)


def criar_campanha_email(request):
    """Cria uma nova campanha de email"""
    
    if request.method == 'POST':
        # Obter dados do formulário (FORA do transaction.atomic)
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao', '')
        template_email_id = request.POST.get('template_email')
        configuracao_servidor_id = request.POST.get('configuracao_servidor')
        
        # Fonte de dados (SQL, Execução existente ou Leads)
        fonte_dados = request.POST.get('fonte_dados')  # 'sql', 'execucao' ou 'leads'
        template_sql_id = request.POST.get('template_sql')
        consulta_execucao_id = request.POST.get('consulta_execucao')
        base_leads_id = request.POST.get('base_leads')
        
        # Determinar tipo_fonte
        if fonte_dados == 'leads':
            tipo_fonte = 'leads'
        else:
            tipo_fonte = 'clientes'
        
        # Configurações SQL + API
        pular_consulta_api = request.POST.get('pular_consulta_api') == 'on'
        credencial_hubsoft_id = request.POST.get('credencial_hubsoft')
        credencial_banco_id = request.POST.get('credencial_banco')
        
        # Variáveis SQL
        valores_variaveis_sql = {}
        if fonte_dados == 'sql' and template_sql_id:
            # Debug: mostrar todos os parâmetros POST
            print(f"DEBUG - Parâmetros POST recebidos:")
            for key, value in request.POST.items():
                if key.startswith('var_'):
                    print(f"  {key} = {value}")
            
            # Coletar valores das variáveis SQL do formulário
            for key, value in request.POST.items():
                if key.startswith('var_'):
                    var_name = key[4:]  # Remove prefixo 'var_'
                    if value.strip():  # Só adiciona se não estiver vazio
                        valores_variaveis_sql[var_name] = value.strip()
            
            print(f"DEBUG - Variáveis SQL coletadas: {valores_variaveis_sql}")
            
            # Verificar se o template tem variáveis esperadas
            if template_sql_id:
                template_sql = TemplateSQL.objects.get(id=template_sql_id)
                
                # USAR O MESMO MÉTODO DO APP CAMPANHAS
                variaveis_config = template_sql.get_variaveis_configuradas()
                print(f"DEBUG - Configuração de variáveis: {variaveis_config}")
                
                # Reprocessar usando a mesma lógica do app campanhas
                valores_variaveis_sql_corrigido = {}
                for var_name, config in variaveis_config.items():
                    valor = request.POST.get(f'var_{var_name}')
                    
                    if config.get('obrigatorio', True) and not valor:
                        print(f"DEBUG - ERRO: Variável obrigatória '{var_name}' não fornecida")
                    
                    # Usar valor padrão se não fornecido e não obrigatório
                    if not valor and not config.get('obrigatorio', True):
                        valor = config.get('valor_padrao', '')
                    
                    if valor:
                        valores_variaveis_sql_corrigido[var_name] = valor
                
                # Atualizar com os valores corrigidos
                valores_variaveis_sql = valores_variaveis_sql_corrigido
                print(f"DEBUG - Variáveis SQL corrigidas: {valores_variaveis_sql}")
        
        # Tipo de agendamento
        tipo_agendamento = request.POST.get('tipo_agendamento', 'uma_vez')
        data_agendamento = request.POST.get('data_agendamento')
        executar_imediatamente = request.POST.get('executar_imediatamente') == 'on'
        
        # Configurações de recorrência
        intervalo_recorrencia = int(request.POST.get('intervalo_recorrencia', 1))
        hora_execucao_str = request.POST.get('hora_execucao') or request.POST.get('hora_execucao_semanal') or request.POST.get('hora_execucao_mensal')
        dias_semana_list = request.POST.getlist('dias_semana')
        dia_mes_recorrencia = request.POST.get('dia_mes_recorrencia')
        expressao_cron = request.POST.get('expressao_cron', '')
        data_fim_recorrencia_str = request.POST.get('data_fim_recorrencia')
        
        # Validações básicas
        if not nome:
            messages.error(request, 'Nome da campanha é obrigatório')
            return redirect('emails:criar_campanha')
        
        if not template_email_id:
            messages.error(request, 'Template de email é obrigatório')
            return redirect('emails:criar_campanha')
        
        if not configuracao_servidor_id:
            messages.error(request, 'Configuração SMTP é obrigatória')
            return redirect('emails:criar_campanha')
        
        # ====================================================================================
        # IMPORTAÇÃO DE LEADS (FORA DO TRANSACTION.ATOMIC PARA EVITAR PROBLEMAS)
        # ====================================================================================
        base_leads_obj = None
        if fonte_dados == 'leads':
            # Verificar se foi enviado um arquivo CSV novo
            if 'arquivo_csv' in request.FILES:
                arquivo_csv = request.FILES['arquivo_csv']
                
                # Validar extensão
                if not arquivo_csv.name.lower().endswith('.csv'):
                    messages.error(request, 'Arquivo deve ser um CSV (.csv)')
                    return redirect('emails:criar_campanha')
                
                # Extrair colunas do CSV
                try:
                    colunas, primeira_linha, total_linhas = ServicoImportacaoCSV.extrair_colunas(arquivo_csv)
                except Exception as e:
                    messages.error(request, f'Erro ao processar arquivo CSV: {str(e)}')
                    return redirect('emails:criar_campanha')
                
                if not colunas:
                    messages.error(request, 'Nenhuma coluna encontrada no arquivo CSV')
                    return redirect('emails:criar_campanha')
                
                # Obter mapeamento do formulário
                coluna_email = request.POST.get('coluna_email_leads')
                coluna_nome = request.POST.get('coluna_nome_leads')
                
                if not coluna_email or not coluna_nome:
                    messages.error(request, 'É necessário mapear as colunas de email e nome do CSV')
                    # Redesenhar formulário com dados do CSV
                    context = {
                        'templates_email': TemplateEmail.objects.filter(ativo=True),
                        'configuracoes_servidor': ConfiguracaoServidorEmail.objects.filter(ativo=True),
                        'templates_sql': TemplateSQL.objects.filter(ativo=True),
                        'execucoes_recentes': ConsultaExecucao.objects.filter(status='concluida').order_by('-data_fim')[:10],
                        'credenciais_banco': CredenciaisBancoDados.objects.filter(ativo=True),
                        'credenciais_hubsoft': CredenciaisHubsoft.objects.filter(ativo=True),
                        'bases_leads': BaseLeads.objects.filter(ativo=True).order_by('-data_importacao'),
                        'tipo_agendamento_choices': CampanhaEmail.TIPO_AGENDAMENTO_CHOICES,
                        'csv_uploaded': True,
                        'csv_colunas': colunas,
                        'csv_preview': ServicoImportacaoCSV.obter_preview_dados(arquivo_csv, limite=5),
                        'csv_total_linhas': total_linhas,
                        'csv_arquivo_nome': arquivo_csv.name,
                        'form_data': {
                            'nome': nome,
                            'descricao': descricao,
                            'template_email_id': template_email_id,
                            'configuracao_servidor_id': configuracao_servidor_id,
                        }
                    }
                    # Salvar arquivo temporariamente na sessão
                    arquivo_csv.seek(0)
                    request.session['csv_temp_arquivo'] = arquivo_csv.read()
                    request.session['csv_temp_nome'] = arquivo_csv.name
                    return render(request, 'emails/criar_campanha.html', context)
                
                # Criar arquivo temporário a partir do upload
                from io import BytesIO
                arquivo_csv.seek(0)
                arquivo_temp = BytesIO(arquivo_csv.read())
                arquivo_temp.name = arquivo_csv.name
                
                # Importar leads e criar base (COM SEU PRÓPRIO TRANSACTION.ATOMIC)
                try:
                    nome_base = f"Campanha: {nome} - {timezone.now().strftime('%d/%m/%Y %H:%M')}"
                    with transaction.atomic():
                        base_leads_obj = ServicoImportacaoCSV.importar_leads(
                            arquivo=arquivo_temp,
                            nome_base=nome_base,
                            descricao=f"Base criada automaticamente para campanha: {nome}",
                            coluna_email=coluna_email,
                            coluna_nome=coluna_nome
                        )
                    base_leads_id = base_leads_obj.id
                    messages.success(
                        request, 
                        f'✅ CSV importado com sucesso! {base_leads_obj.total_validos} lead(s) válido(s) importado(s).'
                    )
                except ValidationError as e:
                    messages.error(request, str(e))
                    return redirect('emails:criar_campanha')
                except Exception as e:
                    logger.error(f'Erro ao importar CSV: {str(e)}')
                    messages.error(request, f'Erro ao importar CSV: {str(e)}')
                    return redirect('emails:criar_campanha')
            elif base_leads_id:
                # Usar base existente
                try:
                    base_leads_obj = BaseLeads.objects.get(id=base_leads_id)
                except BaseLeads.DoesNotExist:
                    messages.error(request, 'Base de leads selecionada não encontrada')
                    return redirect('emails:criar_campanha')
            else:
                messages.error(request, 'É necessário selecionar uma base de leads existente ou fazer upload de um novo CSV')
                return redirect('emails:criar_campanha')
        
        if fonte_dados == 'sql' and not template_sql_id:
            messages.error(request, 'Template SQL é obrigatório quando fonte é SQL')
            return redirect('emails:criar_campanha')
            
        if fonte_dados == 'execucao' and not consulta_execucao_id:
            messages.error(request, 'Consulta Execução é obrigatória quando fonte é execução existente')
            return redirect('emails:criar_campanha')
        
        # Preparar data de agendamento
        if executar_imediatamente:
            data_agendamento_obj = timezone.now()
            status_inicial = 'agendada'
        elif data_agendamento:
            data_agendamento_obj = datetime.strptime(data_agendamento, '%Y-%m-%dT%H:%M')
            if timezone.is_naive(data_agendamento_obj):
                data_agendamento_obj = timezone.make_aware(data_agendamento_obj)
            status_inicial = 'agendada'
        else:
            data_agendamento_obj = None
            status_inicial = 'rascunho'
        
        # Processar configurações de recorrência
        hora_execucao_obj = None
        if hora_execucao_str:
            try:
                hora_execucao_obj = datetime.strptime(hora_execucao_str, '%H:%M').time()
            except ValueError:
                pass
        
        data_fim_recorrencia_obj = None
        if data_fim_recorrencia_str:
            try:
                data_fim_recorrencia_obj = datetime.strptime(data_fim_recorrencia_str, '%Y-%m-%dT%H:%M')
                if timezone.is_naive(data_fim_recorrencia_obj):
                    data_fim_recorrencia_obj = timezone.make_aware(data_fim_recorrencia_obj)
            except ValueError:
                pass
        
        dias_semana_str = ','.join(dias_semana_list) if dias_semana_list else ''
        
        # ====================================================================================
        # CRIAR CAMPANHA (COM TRANSACTION.ATOMIC SEPARADO)
        # ====================================================================================
        try:
            with transaction.atomic():
                # Criar campanha
                campanha = CampanhaEmail.objects.create(
                    nome=nome,
                    descricao=descricao,
                    template_email_id=template_email_id,
                    configuracao_servidor_id=configuracao_servidor_id,
                    tipo_fonte=tipo_fonte,
                    template_sql_id=template_sql_id if fonte_dados == 'sql' else None,
                    consulta_execucao_id=consulta_execucao_id if fonte_dados == 'execucao' else None,
                    base_leads=base_leads_obj if fonte_dados == 'leads' else None,
                    valores_variaveis_sql=valores_variaveis_sql,
                    pular_consulta_api=pular_consulta_api,
                    credencial_hubsoft_id=credencial_hubsoft_id if not pular_consulta_api else None,
                    credencial_banco_id=credencial_banco_id if fonte_dados == 'sql' else None,
                    tipo_agendamento=tipo_agendamento,
                    data_agendamento=data_agendamento_obj,
                    # Campos de recorrência
                    intervalo_recorrencia=intervalo_recorrencia,
                    hora_execucao=hora_execucao_obj,
                    dias_semana_recorrencia=dias_semana_str,
                    dia_mes_recorrencia=int(dia_mes_recorrencia) if dia_mes_recorrencia else None,
                    expressao_cron=expressao_cron,
                    data_fim_recorrencia=data_fim_recorrencia_obj,
                    ativa_recorrencia=True,
                    status=status_inicial,
                    ativo=True
                )
                
                # Calcular próxima execução para campanhas recorrentes
                if tipo_agendamento != 'unico':
                    campanha.atualizar_proxima_execucao()
            
            # TRANSACTION.ATOMIC TERMINA AQUI
            # Processamento em background FORA do atomic para evitar locks
            
            # INICIAR PROCESSAMENTO EM BACKGROUND
            if campanha.tipo_fonte == 'leads' or campanha.template_sql or campanha.consulta_execucao:
                # Atualizar status para processando
                campanha.status = 'processando'
                campanha.save()
                
                # Executar processamento em background
                import threading
                def processar_campanha_background():
                    try:
                        from .executor_integrado import ExecutorCampanhaIntegrado
                        
                        executor = ExecutorCampanhaIntegrado(campanha)
                        dados_clientes = executor._obter_dados_clientes_integrado()
                        
                        if dados_clientes:
                            campanha.total_destinatarios = len(dados_clientes)
                            campanha.status = 'agendada' if not executar_imediatamente else 'executando'
                            campanha.save()
                            
                            # Executar campanha se solicitado
                            if executar_imediatamente:
                                from .executor_integrado import iniciar_campanha_email_async
                                campanha.atualizar_status('executando', 'Execução iniciada automaticamente após criação')
                                iniciar_campanha_email_async(campanha.id)
                        else:
                            campanha.status = 'erro'
                            campanha.save()
                            
                    except Exception as e:
                        campanha.status = 'erro'
                        campanha.save()
                        logger.error(f"Erro ao processar campanha {campanha.id}: {str(e)}")
                
                # Iniciar thread em background
                thread = threading.Thread(target=processar_campanha_background)
                thread.daemon = True
                thread.start()
                
                messages.success(request, f'Campanha "{nome}" criada! O processamento dos dados foi iniciado em background.')
            else:
                messages.success(request, f'Campanha "{nome}" criada como rascunho!')
            
            return redirect('emails:detalhe_campanha', campanha_id=campanha.id)
            
        except Exception as e:
            logger.error(f'Erro ao criar campanha: {str(e)}')
            messages.error(request, f'Erro ao criar campanha: {str(e)}')
            return redirect('emails:criar_campanha')
    
    # GET - Mostrar formulário
    templates_email = TemplateEmail.objects.filter(ativo=True)
    configuracoes_servidor = ConfiguracaoServidorEmail.objects.filter(ativo=True)
    
    # Dados para integração SQL + API
    from campanhas.models import CredenciaisBancoDados, CredenciaisHubsoft
    credenciais_banco = CredenciaisBancoDados.objects.filter(ativo=True)
    credenciais_hubsoft = CredenciaisHubsoft.objects.filter(ativo=True)
    templates_sql = TemplateSQL.objects.filter(ativo=True)
    execucoes_recentes = ConsultaExecucao.objects.filter(
        status='concluida'
    ).order_by('-data_fim')[:10]
    
    # NOVO: Bases de leads disponíveis
    bases_leads = BaseLeads.objects.filter(ativo=True).order_by('-data_importacao')
    
    # Pre-selecionar base se veio via query parameter
    base_leads_presel = request.GET.get('base_leads')
    
    # Bases de leads disponíveis
    bases_leads = BaseLeads.objects.filter(ativo=True).order_by('-data_importacao')
    
    # DEBUG: Log para verificar dados
    print(f"🔍 DEBUG CRIAR CAMPANHA:")
    print(f"  - Templates Email: {templates_email.count()}")
    print(f"  - Configurações SMTP: {configuracoes_servidor.count()}")
    print(f"  - Templates SQL: {templates_sql.count()}")
    print(f"  - Execuções Recentes: {execucoes_recentes.count()}")
    
    if templates_sql.exists():
        print(f"  - Templates SQL encontrados:")
        for t in templates_sql:
            print(f"    • {t.titulo} (ID: {t.id})")
    else:
        print(f"  - ❌ NENHUM TEMPLATE SQL ATIVO ENCONTRADO!")
        
    if execucoes_recentes.exists():
        print(f"  - Execuções encontradas:")
        for e in execucoes_recentes:
            print(f"    • {e.titulo} (ID: {e.id}) - {e.data_fim}")
    else:
        print(f"  - ❌ NENHUMA EXECUÇÃO CONCLUÍDA ENCONTRADA!")
    
    context = {
        'templates_email': templates_email,
        'configuracoes_servidor': configuracoes_servidor,
        'templates_sql': templates_sql,
        'execucoes_recentes': execucoes_recentes,
        'credenciais_banco': credenciais_banco,
        'credenciais_hubsoft': credenciais_hubsoft,
        'bases_leads': bases_leads,
        'tipo_agendamento_choices': CampanhaEmail.TIPO_AGENDAMENTO_CHOICES,
    }
    
    return render(request, 'emails/criar_campanha.html', context)


def obter_variaveis_template_sql(request, template_id):
    """API para obter variáveis de um template SQL (AJAX)"""
    try:
        template = get_object_or_404(TemplateSQL, id=template_id)
        
        # Extrair variáveis do SQL
        variaveis_encontradas = template.extrair_variaveis_do_sql()
        
        # Obter configuração das variáveis (se existir)
        variaveis_config = template.variaveis_config or {}
        
        # Preparar resposta
        variaveis_resposta = {}
        for var_name in variaveis_encontradas:
            config = variaveis_config.get(var_name, {})
            variaveis_resposta[var_name] = {
                'nome': var_name,
                'label': config.get('label', var_name.replace('_', ' ').title()),
                'tipo': config.get('tipo', 'text'),
                'obrigatorio': config.get('obrigatorio', True),
                'valor_padrao': config.get('valor_padrao', ''),
                'opcoes': config.get('opcoes', '').split('\n') if config.get('opcoes') else []
            }
        
        return JsonResponse({
            'status': 'success',
            'variaveis': variaveis_resposta,
            'total': len(variaveis_resposta)
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


def detalhe_campanha_email(request, campanha_id):
    """Exibe detalhes de uma campanha específica"""
    
    campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
    
    # Obter estatísticas detalhadas
    stats = obter_estatisticas_campanha(campanha_id)
    
    # Envios individuais recentes
    envios_recentes = EnvioEmailIndividual.objects.filter(
        campanha=campanha
    ).select_related('cliente').order_by('-data_envio')[:10]
    
    # Logs recentes
    logs_recentes = LogEnvioEmail.objects.filter(
        campanha=campanha
    ).order_by('-data_criacao')[:20]
    
    context = {
        'campanha': campanha,
        'stats': stats,
        'envios_recentes': envios_recentes,
        'logs_recentes': logs_recentes,
    }
    
    return render(request, 'emails/detalhe_campanha.html', context)


def configurar_campanha_email(request, campanha_id):
    """Configura uma campanha existente"""
    
    campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Atualizar dados básicos
                campanha.nome = request.POST.get('nome', campanha.nome)
                campanha.descricao = request.POST.get('descricao', campanha.descricao)
                
                # Atualizar status se solicitado
                novo_status = request.POST.get('status')
                if novo_status and novo_status in [choice[0] for choice in CampanhaEmail.STATUS_CHOICES]:
                    if novo_status == 'agendada' and campanha.pode_executar():
                        campanha.status = novo_status
                    elif novo_status in ['pausada', 'cancelada']:
                        campanha.status = novo_status
                
                campanha.save()
                
                messages.success(request, 'Campanha configurada com sucesso!')
                return redirect('emails:detalhe_campanha', campanha_id=campanha.id)
                
        except Exception as e:
            messages.error(request, f'Erro ao configurar campanha: {str(e)}')
    
    context = {
        'campanha': campanha,
        'status_choices': CampanhaEmail.STATUS_CHOICES,
    }
    
    return render(request, 'emails/configurar_campanha.html', context)


def executar_campanha_email(request, campanha_id):
    """Executa uma campanha de email manualmente"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
        
        if not campanha.pode_executar():
            return JsonResponse({
                'error': 'Campanha não pode ser executada. Verifique as configurações.'
            }, status=400)
        
        # Executar em thread separada para não bloquear a interface
        import threading
        
        # Usar executor integrado
        from .executor_integrado import iniciar_campanha_email_async
        
        # Atualizar status imediatamente
        campanha.atualizar_status('executando', 'Execução iniciada manualmente via interface')
        
        # Iniciar execução em background
        thread = iniciar_campanha_email_async(campanha.id)
        
        return JsonResponse({
            'success': True,
            'message': 'Execução iniciada com sucesso'
        })
        
    except Exception as e:
        logger.error(f'Erro ao executar campanha {campanha_id}: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)


def pausar_campanha_email(request, campanha_id):
    """Pausa uma campanha em execução"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
        
        if campanha.status not in ['executando', 'agendada']:
            return JsonResponse({
                'error': 'Campanha não pode ser pausada no status atual'
            }, status=400)
        
        # Para campanhas recorrentes, pausar significa parar as próximas execuções
        if campanha.tipo_agendamento != 'unico':
            campanha.ativo = False  # Desativar para o serviço de monitoramento
            campanha.atualizar_status('pausada', 'Campanha recorrente pausada - próximas execuções canceladas')
            message = 'Campanha recorrente pausada. As próximas execuções automáticas foram canceladas.'
        else:
            campanha.atualizar_status('pausada', 'Campanha pausada manualmente')
            message = 'Campanha pausada com sucesso'
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def cancelar_campanha_email(request, campanha_id):
    """Cancela uma campanha"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
        
        if campanha.status in ['concluida', 'cancelada']:
            return JsonResponse({
                'error': 'Campanha já foi finalizada'
            }, status=400)
        
        # Desativar campanha para o serviço de monitoramento
        campanha.ativo = False
        
        # Cancelar campanha
        campanha.atualizar_status('cancelada', 'Campanha cancelada manualmente')
        
        # Se estiver executando, marcar como cancelada imediatamente
        if campanha.status == 'executando':
            campanha.data_fim_execucao = timezone.now()
            campanha.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Campanha cancelada com sucesso'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def retomar_campanha_email(request, campanha_id):
    """Retoma uma campanha pausada"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
        
        if campanha.status != 'pausada':
            return JsonResponse({
                'error': 'Apenas campanhas pausadas podem ser retomadas'
            }, status=400)
        
        # Reativar campanha para o serviço de monitoramento
        campanha.ativo = True
        
        # Para campanhas recorrentes, agendar próxima execução
        if campanha.tipo_agendamento != 'unico':
            campanha.proxima_execucao = campanha.calcular_proxima_execucao()
            campanha.atualizar_status('agendada', 'Campanha recorrente retomada - próxima execução agendada')
            message = 'Campanha recorrente retomada. Próxima execução agendada.'
        else:
            campanha.atualizar_status('agendada', 'Campanha retomada manualmente')
            message = 'Campanha retomada com sucesso'
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def status_campanha_ajax(request, campanha_id):
    """Retorna status atual da campanha via AJAX"""
    
    try:
        campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
        stats = obter_estatisticas_campanha(campanha_id)
        
        return JsonResponse({
            'status': campanha.status,
            'status_display': campanha.get_status_display(),
            'progresso': campanha.get_progresso_percentual(),
            'taxa_sucesso': campanha.get_taxa_sucesso(),
            'total_destinatarios': campanha.total_destinatarios,
            'total_enviados': campanha.total_enviados,
            'total_sucessos': campanha.total_sucessos,
            'total_erros': campanha.total_erros,
            'total_pendentes': campanha.total_pendentes,
            'pode_executar': campanha.pode_executar(),
            'stats': stats
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def listar_templates_email(request):
    """Lista todos os templates de email"""
    
    search = request.GET.get('search', '')
    tipo_filter = request.GET.get('tipo', '')
    
    templates = TemplateEmail.objects.all()
    
    if search:
        templates = templates.filter(
            Q(nome__icontains=search) |
            Q(assunto__icontains=search) |
            Q(descricao__icontains=search)
        )
    
    if tipo_filter:
        templates = templates.filter(tipo=tipo_filter)
    
    templates = templates.order_by('-data_criacao')
    
    # Paginação
    paginator = Paginator(templates, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'tipo_filter': tipo_filter,
        'tipo_choices': TemplateEmail.TIPO_TEMPLATE_CHOICES,
    }
    
    return render(request, 'emails/listar_templates.html', context)


def visualizar_template_email(request, template_id):
    """Visualiza um template de email com dados de exemplo"""
    
    template = get_object_or_404(TemplateEmail, id=template_id)
    
    # Dados de exemplo para preview
    dados_exemplo = {
        'codigo_cliente': '12345',
        'nome_razaosocial': 'João Silva',
        'telefone_corrigido': '(11) 99999-9999',
        'id_fatura': 'FAT-2024-001',
        'vencimento_fatura': '15/01/2024',
        'valor_fatura': '150,00',
        'pix': '12345678901',
        'codigo_barras': '12345.67890 12345.678901 12345.678901 1 23456789012345',
        'link_boleto': 'https://exemplo.com/boleto/123',
        'dados_dinamicos': {
            'endereco': 'Rua das Flores, 123',
            'cidade': 'São Paulo',
            'email': 'joao@exemplo.com'
        }
    }
    
    # Renderizar template com dados de exemplo
    template_renderizado = template.renderizar_template(dados_exemplo)
    
    context = {
        'template': template,
        'template_renderizado': template_renderizado,
        'variaveis_detectadas': template.extrair_variaveis_do_template(),
        'dados_exemplo': dados_exemplo,
    }
    
    return render(request, 'emails/visualizar_template.html', context)


def testar_configuracao_smtp_ajax(request, config_id):
    """Testa uma configuração SMTP via AJAX"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        sucesso, mensagem = testar_configuracao_smtp(config_id)
        
        return JsonResponse({
            'success': sucesso,
            'message': mensagem
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao testar configuração: {str(e)}'
        }, status=500)


def exportar_resultados_campanha(request, campanha_id):
    """Exporta resultados de uma campanha para CSV"""
    
    campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
    
    # Criar response CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="campanha_{campanha.id}_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    
    # Escrever BOM para UTF-8
    response.write('\ufeff')
    
    import csv
    writer = csv.writer(response)
    
    # Cabeçalho
    writer.writerow([
        'Cliente', 'Email', 'Nome', 'Status', 'Data Envio', 
        'Tentativas', 'Erro', 'Message ID'
    ])
    
    # Dados
    envios = EnvioEmailIndividual.objects.filter(
        campanha=campanha
    ).select_related('cliente').order_by('-data_envio')
    
    for envio in envios:
        writer.writerow([
            envio.cliente.codigo_cliente,
            envio.email_destinatario,
            envio.nome_destinatario,
            envio.get_status_display(),
            envio.data_envio.strftime('%d/%m/%Y %H:%M') if envio.data_envio else '',
            envio.tentativas,
            envio.erro_detalhado[:100] if envio.erro_detalhado else '',
            envio.message_id
        ])
    
    return response


def progresso_campanha_ajax(request, campanha_id):
    """Retorna progresso detalhado da campanha incluindo consulta SQL"""
    
    try:
        campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
        
        # Dados da campanha
        total_destinatarios = campanha.total_destinatarios or 0
        total_enviados = campanha.total_enviados or 0
        total_sucessos = campanha.total_sucessos or 0
        total_erros = campanha.total_erros or 0
        
        # Progresso geral
        if total_destinatarios > 0:
            progresso_envio = round((total_enviados / total_destinatarios) * 100, 1)
        else:
            progresso_envio = 0
        
        # Status da consulta
        consulta_info = {}
        if campanha.consulta_execucao:
            consulta = campanha.consulta_execucao
            consulta_info = {
                'id': consulta.id,
                'titulo': consulta.titulo,
                'status': consulta.status,
                'status_display': consulta.get_status_display(),
                'total_registros_sql': consulta.total_registros_sql or 0,
                'data_inicio': consulta.data_inicio.strftime('%d/%m/%Y %H:%M:%S') if consulta.data_inicio else None,
                'data_fim': consulta.data_fim.strftime('%d/%m/%Y %H:%M:%S') if consulta.data_fim else None
            }
        elif campanha.template_sql:
            consulta_info = {
                'titulo': f"SQL Dinâmico - {campanha.template_sql.titulo}",
                'status': 'sql_template',
                'status_display': 'Template SQL Configurado'
            }
        
        # Logs da execução
        logs_execucao = []
        if campanha.log_execucao:
            linhas = campanha.log_execucao.split('\n')
            logs_execucao = [linha.strip() for linha in linhas if linha.strip()]
        
        # Envios recentes
        envios_recentes = EnvioEmailIndividual.objects.filter(
            campanha=campanha
        ).order_by('-data_envio')[:10]
        
        envios_dados = []
        for envio in envios_recentes:
            envios_dados.append({
                'nome': envio.nome_destinatario,
                'email': envio.email_destinatario,
                'status': envio.status,
                'status_display': envio.get_status_display(),
                'data_envio': envio.data_envio.strftime('%d/%m/%Y %H:%M:%S') if envio.data_envio else None,
                'erro': envio.erro_detalhado[:100] + '...' if envio.erro_detalhado and len(envio.erro_detalhado) > 100 else envio.erro_detalhado
            })
        
        return JsonResponse({
            'campanha': {
                'id': campanha.id,
                'nome': campanha.nome,
                'status': campanha.status,
                'status_display': campanha.get_status_display()
            },
            'estatisticas': {
                'total_destinatarios': total_destinatarios,
                'total_enviados': total_enviados,
                'total_sucessos': total_sucessos,
                'total_erros': total_erros,
                'total_pendentes': total_destinatarios - total_enviados,
                'progresso_envio': progresso_envio,
                'taxa_sucesso': round((total_sucessos / total_enviados) * 100, 1) if total_enviados > 0 else 0
            },
            'consulta': consulta_info,
            'logs': logs_execucao[-20:],  # Últimas 20 linhas
            'envios_recentes': envios_dados,
            'timestamps': {
                'data_inicio': campanha.data_inicio_execucao.strftime('%d/%m/%Y %H:%M:%S') if campanha.data_inicio_execucao else None,
                'data_fim': campanha.data_fim_execucao.strftime('%d/%m/%Y %H:%M:%S') if campanha.data_fim_execucao else None
            },
            'acoes_disponiveis': {
                'pode_executar': campanha.status in ['rascunho', 'agendada', 'pausada'] and campanha.ativo,
                'pode_pausar': campanha.status == 'executando',
                'pode_cancelar': campanha.status in ['agendada', 'executando', 'pausada'],
                'esta_executando': campanha.status == 'executando'
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def processar_consulta_campanha(request, campanha_id):
    """Processa a consulta SQL de uma campanha (similar ao sistema existente)"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
        
        if not campanha.template_sql:
            return JsonResponse({
                'error': 'Campanha não possui Template SQL configurado'
            }, status=400)
        
        # Usar o executor integrado para processar apenas a consulta
        from .executor_integrado import ExecutorCampanhaIntegrado
        
        executor = ExecutorCampanhaIntegrado(campanha)
        
        # Executar apenas a parte de obtenção de dados
        dados_clientes = executor._obter_dados_clientes_integrado()
        
        if dados_clientes:
            campanha.total_destinatarios = len(dados_clientes)
            campanha.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Consulta processada: {len(dados_clientes)} clientes encontrados com email',
                'total_clientes': len(dados_clientes),
                'consulta_id': campanha.consulta_execucao.id if campanha.consulta_execucao else None
            })
        else:
            return JsonResponse({
                'error': 'Nenhum cliente encontrado com email válido'
            }, status=400)
        
    except Exception as e:
        logger.error(f'Erro ao processar consulta da campanha {campanha_id}: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_criar_campanha_execucao_unica(request):
    """
    API para criar campanha de execução única usando execução existente
    
    Parâmetros esperados:
    - id_execucao: ID da execução existente
    - template_email: ID do template de email
    - servidor_email: ID da configuração do servidor SMTP
    - titulo: Título da campanha
    
    Retorna:
    - success: boolean
    - campanha_id: ID da campanha criada
    - message: Mensagem de sucesso/erro
    """
    try:
        # Obter dados do JSON
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'JSON inválido'
            }, status=400)
        
        # Validar parâmetros obrigatórios
        id_execucao = data.get('id_execucao')
        template_email_id = data.get('template_email')
        servidor_email_id = data.get('servidor_email')
        titulo = data.get('titulo')
        
        if not all([id_execucao, template_email_id, servidor_email_id, titulo]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios: id_execucao, template_email, servidor_email, titulo'
            }, status=400)
        
        # Validar se a execução existe e está concluída
        try:
            execucao = ConsultaExecucao.objects.get(id=id_execucao)
        except ConsultaExecucao.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Execução com ID {id_execucao} não encontrada'
            }, status=404)
        
        if execucao.status != 'concluida':
            return JsonResponse({
                'success': False,
                'error': f'Execução deve estar concluída. Status atual: {execucao.get_status_display()}'
            }, status=400)
        
        # Validar template de email
        try:
            template_email = TemplateEmail.objects.get(id=template_email_id, ativo=True)
        except TemplateEmail.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Template de email com ID {template_email_id} não encontrado ou inativo'
            }, status=404)
        
        # Validar configuração do servidor
        try:
            configuracao_servidor = ConfiguracaoServidorEmail.objects.get(id=servidor_email_id, ativo=True)
        except ConfiguracaoServidorEmail.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Configuração de servidor com ID {servidor_email_id} não encontrada ou inativa'
            }, status=404)
        
        # Criar campanha usando transação
        with transaction.atomic():
            campanha = CampanhaEmail.objects.create(
                nome=titulo,
                descricao=f'Campanha criada via API para execução {execucao.id}',
                template_email=template_email,
                configuracao_servidor=configuracao_servidor,
                consulta_execucao=execucao,
                tipo_agendamento='unico',
                data_agendamento=timezone.now(),  # Executar imediatamente
                status='agendada',
                ativo=True,
                pular_consulta_api=execucao.pular_consulta_api  # Usar mesma configuração da execução
            )
            
            # Obter total de destinatários da execução
            from campanhas.models import ConsultaCliente
            
            if execucao.pular_consulta_api:
                # Se API foi pulada, considera todos os clientes da execução
                total_clientes = ConsultaCliente.objects.filter(execucao=execucao).count()
            else:
                # Se API foi consultada, considera apenas sucessos
                total_clientes = ConsultaCliente.objects.filter(
                    execucao=execucao,
                    sucesso_api=True
                ).count()
            
            campanha.total_destinatarios = total_clientes
            campanha.save()
            
            # Executar envio de emails imediatamente
            try:
                campanha.atualizar_status('executando', 'Execução iniciada via API')
                
                # Usar o executor integrado para enviar emails imediatamente
                from .executor_integrado import ExecutorCampanhaIntegrado
                
                executor = ExecutorCampanhaIntegrado(campanha)
                
                # Executar envio de emails
                sucesso = executor.executar_campanha_completa()
                
                if sucesso:
                    campanha.atualizar_status('concluida', 'Execução concluída via API com sucesso')
                    mensagem_final = f'Campanha criada e executada com sucesso. Total: {campanha.total_enviados} enviados, {campanha.total_sucessos} sucessos, {campanha.total_erros} erros'
                else:
                    campanha.atualizar_status('erro', 'Erro na execução da campanha')
                    mensagem_final = f'Campanha criada mas houve erro na execução. Total: {campanha.total_enviados} enviados, {campanha.total_sucessos} sucessos, {campanha.total_erros} erros'
                
            except Exception as e:
                campanha.atualizar_status('erro', f'Erro na execução: {str(e)}')
                logger.error(f'Erro ao executar campanha {campanha.id} via API: {str(e)}')
                mensagem_final = f'Campanha criada mas houve erro na execução: {str(e)}'
            
            # Atualizar dados finais da campanha
            campanha.refresh_from_db()
            
            return JsonResponse({
                'success': True,
                'campanha_id': campanha.id,
                'message': mensagem_final,
                'dados': {
                    'id': campanha.id,
                    'nome': campanha.nome,
                    'status': campanha.get_status_display(),
                    'total_destinatarios': campanha.total_destinatarios,
                    'total_enviados': campanha.total_enviados,
                    'total_sucessos': campanha.total_sucessos,
                    'total_erros': campanha.total_erros,
                    'template_email': template_email.nome,
                    'servidor_email': configuracao_servidor.nome,
                    'execucao_origem': execucao.titulo,
                    'data_inicio_execucao': campanha.data_inicio_execucao.isoformat() if campanha.data_inicio_execucao else None,
                    'data_fim_execucao': campanha.data_fim_execucao.isoformat() if campanha.data_fim_execucao else None
                }
            })
            
    except Exception as e:
        logger.error(f'Erro na API criar_campanha_execucao_unica: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_listar_campanhas(request):
    """
    API para listar campanhas de email
    
    Parâmetros opcionais:
    - status: Filtrar por status (rascunho, agendada, executando, pausada, concluida, cancelada, erro)
    - search: Buscar por nome ou descrição
    - page: Número da página (padrão: 1)
    - limit: Itens por página (padrão: 20, máximo: 100)
    """
    try:
        # Parâmetros de filtro
        status_filter = request.GET.get('status', '')
        search = request.GET.get('search', '')
        page = int(request.GET.get('page', 1))
        limit = min(int(request.GET.get('limit', 20)), 100)  # Máximo 100 itens
        
        # Query base
        campanhas = CampanhaEmail.objects.select_related(
            'template_email', 'configuracao_servidor', 'consulta_execucao'
        ).order_by('-data_criacao')
        
        # Aplicar filtros
        if status_filter:
            campanhas = campanhas.filter(status=status_filter)
        
        if search:
            campanhas = campanhas.filter(
                Q(nome__icontains=search) |
                Q(descricao__icontains=search) |
                Q(template_email__nome__icontains=search)
            )
        
        # Paginação
        from django.core.paginator import Paginator
        paginator = Paginator(campanhas, limit)
        page_obj = paginator.get_page(page)
        
        # Preparar dados das campanhas
        campanhas_data = []
        for campanha in page_obj:
            campanhas_data.append({
                'id': campanha.id,
                'nome': campanha.nome,
                'descricao': campanha.descricao,
                'status': campanha.status,
                'status_display': campanha.get_status_display(),
                'tipo_agendamento': campanha.tipo_agendamento,
                'tipo_agendamento_display': campanha.get_tipo_agendamento_display(),
                'ativo': campanha.ativo,
                'total_destinatarios': campanha.total_destinatarios,
                'total_enviados': campanha.total_enviados,
                'total_sucessos': campanha.total_sucessos,
                'total_erros': campanha.total_erros,
                'taxa_sucesso': campanha.get_taxa_sucesso(),
                'data_criacao': campanha.data_criacao.isoformat(),
                'data_agendamento': campanha.data_agendamento.isoformat() if campanha.data_agendamento else None,
                'data_inicio_execucao': campanha.data_inicio_execucao.isoformat() if campanha.data_inicio_execucao else None,
                'data_fim_execucao': campanha.data_fim_execucao.isoformat() if campanha.data_fim_execucao else None,
                'proxima_execucao': campanha.proxima_execucao.isoformat() if campanha.proxima_execucao else None,
                'template_email': {
                    'id': campanha.template_email.id,
                    'nome': campanha.template_email.nome,
                    'tipo': campanha.template_email.tipo
                } if campanha.template_email else None,
                'configuracao_servidor': {
                    'id': campanha.configuracao_servidor.id,
                    'nome': campanha.configuracao_servidor.nome,
                    'servidor': campanha.configuracao_servidor.servidor_smtp
                } if campanha.configuracao_servidor else None,
                'consulta_execucao': {
                    'id': campanha.consulta_execucao.id,
                    'titulo': campanha.consulta_execucao.titulo,
                    'status': campanha.consulta_execucao.status
                } if campanha.consulta_execucao else None
            })
        
        return JsonResponse({
            'success': True,
            'data': campanhas_data,
            'pagination': {
                'page': page_obj.number,
                'pages': paginator.num_pages,
                'total': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
                'previous_page': page_obj.previous_page_number() if page_obj.has_previous() else None
            },
            'filters': {
                'status': status_filter,
                'search': search
            }
        })
        
    except Exception as e:
        logger.error(f'Erro na API listar_campanhas: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_detalhe_campanha(request, campanha_id):
    """
    API para obter detalhes de uma campanha específica
    
    Parâmetros:
    - campanha_id: ID da campanha
    """
    try:
        campanha = get_object_or_404(CampanhaEmail, id=campanha_id)
        
        # Obter estatísticas detalhadas
        stats = obter_estatisticas_campanha(campanha_id)
        
        # Envios individuais recentes
        envios_recentes = EnvioEmailIndividual.objects.filter(
            campanha=campanha
        ).select_related('cliente').order_by('-data_envio')[:10]
        
        # Logs recentes
        logs_recentes = LogEnvioEmail.objects.filter(
            campanha=campanha
        ).order_by('-data_criacao')[:20]
        
        # Preparar dados dos envios
        envios_data = []
        for envio in envios_recentes:
            envios_data.append({
                'id': envio.id,
                'cliente_codigo': envio.cliente.codigo_cliente,
                'email_destinatario': envio.email_destinatario,
                'nome_destinatario': envio.nome_destinatario,
                'status': envio.status,
                'status_display': envio.get_status_display(),
                'data_envio': envio.data_envio.isoformat() if envio.data_envio else None,
                'tentativas': envio.tentativas,
                'message_id': envio.message_id,
                'erro_detalhado': envio.erro_detalhado
            })
        
        # Preparar dados dos logs
        logs_data = []
        for log in logs_recentes:
            logs_data.append({
                'id': log.id,
                'nivel': log.nivel,
                'acao': log.acao,
                'mensagem': log.mensagem,
                'data_criacao': log.data_criacao.isoformat(),
                'dados_extras': log.dados_extras
            })
        
        return JsonResponse({
            'success': True,
            'data': {
                'id': campanha.id,
                'nome': campanha.nome,
                'descricao': campanha.descricao,
                'status': campanha.status,
                'status_display': campanha.get_status_display(),
                'tipo_agendamento': campanha.tipo_agendamento,
                'tipo_agendamento_display': campanha.get_tipo_agendamento_display(),
                'ativo': campanha.ativo,
                'pular_consulta_api': campanha.pular_consulta_api,
                'total_destinatarios': campanha.total_destinatarios,
                'total_enviados': campanha.total_enviados,
                'total_sucessos': campanha.total_sucessos,
                'total_erros': campanha.total_erros,
                'total_pendentes': campanha.total_pendentes,
                'taxa_sucesso': campanha.get_taxa_sucesso(),
                'progresso_percentual': campanha.get_progresso_percentual(),
                'data_criacao': campanha.data_criacao.isoformat(),
                'data_agendamento': campanha.data_agendamento.isoformat() if campanha.data_agendamento else None,
                'data_inicio_execucao': campanha.data_inicio_execucao.isoformat() if campanha.data_inicio_execucao else None,
                'data_fim_execucao': campanha.data_fim_execucao.isoformat() if campanha.data_fim_execucao else None,
                'proxima_execucao': campanha.proxima_execucao.isoformat() if campanha.proxima_execucao else None,
                'log_execucao': campanha.log_execucao,
                'template_email': {
                    'id': campanha.template_email.id,
                    'nome': campanha.template_email.nome,
                    'tipo': campanha.template_email.tipo,
                    'assunto': campanha.template_email.assunto
                } if campanha.template_email else None,
                'configuracao_servidor': {
                    'id': campanha.configuracao_servidor.id,
                    'nome': campanha.configuracao_servidor.nome,
                    'servidor_smtp': campanha.configuracao_servidor.servidor_smtp,
                    'porta': campanha.configuracao_servidor.porta,
                    'usar_tls': campanha.configuracao_servidor.usar_tls
                } if campanha.configuracao_servidor else None,
                'consulta_execucao': {
                    'id': campanha.consulta_execucao.id,
                    'titulo': campanha.consulta_execucao.titulo,
                    'status': campanha.consulta_execucao.status,
                    'status_display': campanha.consulta_execucao.get_status_display(),
                    'data_inicio': campanha.consulta_execucao.data_inicio.isoformat() if campanha.consulta_execucao.data_inicio else None,
                    'data_fim': campanha.consulta_execucao.data_fim.isoformat() if campanha.consulta_execucao.data_fim else None
                } if campanha.consulta_execucao else None,
                'estatisticas': stats,
                'envios_recentes': envios_data,
                'logs_recentes': logs_data,
                'acoes_disponiveis': {
                    'pode_executar': campanha.pode_executar(),
                    'pode_pausar': campanha.status == 'executando',
                    'pode_cancelar': campanha.status in ['agendada', 'executando', 'pausada'],
                    'pode_retomar': campanha.status == 'pausada'
                }
            }
        })
        
    except Exception as e:
        logger.error(f'Erro na API detalhe_campanha: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_listar_servidores_email(request):
    """
    API para listar configurações de servidores de email
    
    Parâmetros opcionais:
    - ativo: Filtrar apenas servidores ativos (true/false)
    - search: Buscar por nome ou servidor SMTP
    """
    try:
        # Parâmetros de filtro
        ativo_filter = request.GET.get('ativo', '')
        search = request.GET.get('search', '')
        
        # Query base
        servidores = ConfiguracaoServidorEmail.objects.all().order_by('nome')
        
        # Aplicar filtros
        if ativo_filter.lower() == 'true':
            servidores = servidores.filter(ativo=True)
        elif ativo_filter.lower() == 'false':
            servidores = servidores.filter(ativo=False)
        
        if search:
            servidores = servidores.filter(
                Q(nome__icontains=search) |
                Q(servidor_smtp__icontains=search) |
                Q(email_remetente__icontains=search)
            )
        
        # Preparar dados dos servidores
        servidores_data = []
        for servidor in servidores:
            servidores_data.append({
                'id': servidor.id,
                'nome': servidor.nome,
                'servidor_smtp': servidor.servidor_smtp,
                'porta': servidor.porta,
                'usar_tls': servidor.usar_tls,
                'usar_ssl': servidor.usar_ssl,
                'usuario': servidor.usuario,
                'senha': '***' if servidor.senha else None,  # Não expor senha
                'email_remetente': servidor.email_remetente,
                'nome_remetente': servidor.nome_remetente,
                'ativo': servidor.ativo,
                'data_criacao': servidor.data_criacao.isoformat(),
                'ultimo_teste': servidor.data_ultimo_teste.isoformat() if servidor.data_ultimo_teste else None,
                'teste_sucesso': bool(servidor.data_ultimo_teste and servidor.resultado_ultimo_teste)
            })
        
        return JsonResponse({
            'success': True,
            'data': servidores_data,
            'total': len(servidores_data),
            'filters': {
                'ativo': ativo_filter,
                'search': search
            }
        })
        
    except Exception as e:
        logger.error(f'Erro na API listar_servidores_email: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_detalhe_servidor_email(request, servidor_id):
    """
    API para obter detalhes de uma configuração de servidor de email
    
    Parâmetros:
    - servidor_id: ID da configuração do servidor
    """
    try:
        servidor = get_object_or_404(ConfiguracaoServidorEmail, id=servidor_id)
        
        return JsonResponse({
            'success': True,
            'data': {
                'id': servidor.id,
                'nome': servidor.nome,
                'servidor_smtp': servidor.servidor_smtp,
                'porta': servidor.porta,
                'usar_tls': servidor.usar_tls,
                'usar_ssl': servidor.usar_ssl,
                'usuario': servidor.usuario,
                'senha': '***' if servidor.senha else None,  # Não expor senha
                'email_remetente': servidor.email_remetente,
                'nome_remetente': servidor.nome_remetente,
                'ativo': servidor.ativo,
                'data_criacao': servidor.data_criacao.isoformat(),
                'ultimo_teste': servidor.data_ultimo_teste.isoformat() if servidor.data_ultimo_teste else None,
                'teste_sucesso': bool(servidor.data_ultimo_teste and servidor.resultado_ultimo_teste),
                'log_teste': servidor.resultado_ultimo_teste,
                'campanhas_ativas': CampanhaEmail.objects.filter(
                    configuracao_servidor=servidor,
                    ativo=True
                ).count(),
                'total_campanhas': CampanhaEmail.objects.filter(
                    configuracao_servidor=servidor
                ).count()
            }
        })
        
    except Exception as e:
        logger.error(f'Erro na API detalhe_servidor_email: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_listar_templates_email(request):
    """
    API para listar templates de email
    
    Parâmetros opcionais:
    - ativo: Filtrar apenas templates ativos (true/false)
    - tipo: Filtrar por tipo de template
    - search: Buscar por nome, assunto ou descrição
    """
    try:
        # Parâmetros de filtro
        ativo_filter = request.GET.get('ativo', '')
        tipo_filter = request.GET.get('tipo', '')
        search = request.GET.get('search', '')
        
        # Query base
        templates = TemplateEmail.objects.all().order_by('nome')
        
        # Aplicar filtros
        if ativo_filter.lower() == 'true':
            templates = templates.filter(ativo=True)
        elif ativo_filter.lower() == 'false':
            templates = templates.filter(ativo=False)
        
        if tipo_filter:
            templates = templates.filter(tipo=tipo_filter)
        
        if search:
            templates = templates.filter(
                Q(nome__icontains=search) |
                Q(assunto__icontains=search) |
                Q(descricao__icontains=search)
            )
        
        # Preparar dados dos templates
        templates_data = []
        for template in templates:
            templates_data.append({
                'id': template.id,
                'nome': template.nome,
                'descricao': template.descricao,
                'tipo': template.tipo,
                'tipo_display': template.get_tipo_display(),
                'assunto': template.assunto,
                'corpo_html': template.corpo_html,
                'corpo_texto': template.corpo_texto,
                'ativo': template.ativo,
                'total_enviados': template.total_enviados,
                'data_criacao': template.data_criacao.isoformat(),
                'data_atualizacao': template.data_atualizacao.isoformat(),
                'variaveis_detectadas': template.extrair_variaveis_do_template(),
                'campanhas_ativas': CampanhaEmail.objects.filter(
                    template_email=template,
                    ativo=True
                ).count(),
                'total_campanhas': CampanhaEmail.objects.filter(
                    template_email=template
                ).count()
            })
        
        return JsonResponse({
            'success': True,
            'data': templates_data,
            'total': len(templates_data),
            'filters': {
                'ativo': ativo_filter,
                'tipo': tipo_filter,
                'search': search
            }
        })
        
    except Exception as e:
        logger.error(f'Erro na API listar_templates_email: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_detalhe_template_email(request, template_id):
    """
    API para obter detalhes de um template de email
    
    Parâmetros:
    - template_id: ID do template de email
    """
    try:
        template = get_object_or_404(TemplateEmail, id=template_id)
        
        # Dados de exemplo para preview
        dados_exemplo = {
            'codigo_cliente': '12345',
            'nome_razaosocial': 'João Silva',
            'telefone_corrigido': '(11) 99999-9999',
            'id_fatura': 'FAT-2024-001',
            'vencimento_fatura': '15/01/2024',
            'valor_fatura': '150,00',
            'pix': '12345678901',
            'codigo_barras': '12345.67890 12345.678901 12345.678901 1 23456789012345',
            'link_boleto': 'https://exemplo.com/boleto/123',
            'dados_dinamicos': {
                'endereco': 'Rua das Flores, 123',
                'cidade': 'São Paulo',
                'email': 'joao@exemplo.com'
            }
        }
        
        # Renderizar template com dados de exemplo
        template_renderizado = template.renderizar_template(dados_exemplo)
        
        return JsonResponse({
            'success': True,
            'data': {
                'id': template.id,
                'nome': template.nome,
                'descricao': template.descricao,
                'tipo': template.tipo,
                'tipo_display': template.get_tipo_display(),
                'assunto': template.assunto,
                'corpo_html': template.corpo_html,
                'corpo_texto': template.corpo_texto,
                'ativo': template.ativo,
                'total_enviados': template.total_enviados,
                'data_criacao': template.data_criacao.isoformat(),
                'data_atualizacao': template.data_atualizacao.isoformat(),
                'variaveis_detectadas': template.extrair_variaveis_do_template(),
                'template_renderizado': template_renderizado,
                'dados_exemplo': dados_exemplo,
                'campanhas_ativas': CampanhaEmail.objects.filter(
                    template_email=template,
                    ativo=True
                ).count(),
                'total_campanhas': CampanhaEmail.objects.filter(
                    template_email=template
                ).count()
            }
        })
        
    except Exception as e:
        logger.error(f'Erro na API detalhe_template_email: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


# ==========================================
# VIEWS PARA GESTÃO DE LEADS (CSV)
# ==========================================

def listar_bases_leads(request):
    """Lista todas as bases de leads importadas"""
    
    search = request.GET.get('search', '')
    
    bases = BaseLeads.objects.all()
    
    if search:
        bases = bases.filter(
            Q(nome__icontains=search) |
            Q(descricao__icontains=search) |
            Q(arquivo_original_nome__icontains=search)
        )
    
    bases = bases.order_by('-data_importacao')
    
    # Paginação
    paginator = Paginator(bases, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas gerais
    stats = {
        'total_bases': BaseLeads.objects.count(),
        'bases_ativas': BaseLeads.objects.filter(ativo=True).count(),
        'total_leads': Lead.objects.filter(valido=True).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
    }
    
    return render(request, 'emails/listar_bases_leads.html', context)


def importar_leads_csv(request):
    """
    View para upload e importação de CSV de leads
    Processo em 2 etapas:
    1. Upload e análise do arquivo (mostra preview e sugestões)
    2. Confirmação e importação com mapeamento de colunas
    """
    
    if request.method == 'POST':
        etapa = request.POST.get('etapa', '1')
        
        if etapa == '1':
            # ETAPA 1: Upload e análise do arquivo
            try:
                arquivo = request.FILES.get('arquivo_csv')
                
                if not arquivo:
                    messages.error(request, 'Nenhum arquivo foi enviado')
                    return redirect('emails:importar_leads')
                
                # Validar extensão
                if not arquivo.name.endswith(('.csv', '.CSV')):
                    messages.error(request, 'Apenas arquivos CSV são permitidos')
                    return redirect('emails:importar_leads')
                
                # Analisar CSV
                servico = ServicoImportacaoCSV()
                analise = servico.obter_sugestoes_colunas(arquivo)
                
                # Salvar arquivo temporariamente na sessão (como base64)
                import base64
                arquivo.seek(0)
                arquivo_bytes = arquivo.read()
                arquivo_b64 = base64.b64encode(arquivo_bytes).decode('utf-8')
                
                request.session['arquivo_csv_temp'] = {
                    'nome': arquivo.name,
                    'conteudo': arquivo_b64,
                    'encoding': analise['encoding'],
                    'delimitador': analise['delimitador']
                }
                
                # Ir para etapa 2 (mapeamento)
                context = {
                    'etapa': 2,
                    'arquivo_nome': arquivo.name,
                    'colunas': analise['colunas'],
                    'sugestao_email': analise['sugestao_email'],
                    'sugestao_nome': analise['sugestao_nome'],
                    'preview': analise['preview'],
                    'encoding': analise['encoding'],
                    'delimitador': analise['delimitador'],
                }
                
                return render(request, 'emails/importar_leads.html', context)
                
            except Exception as e:
                messages.error(request, f'Erro ao processar arquivo: {str(e)}')
                return redirect('emails:importar_leads')
        
        elif etapa == '2':
            # ETAPA 2: Confirmar importação com mapeamento
            try:
                # Recuperar arquivo da sessão
                arquivo_temp = request.session.get('arquivo_csv_temp')
                if not arquivo_temp:
                    messages.error(request, 'Sessão expirou. Por favor, faça upload do arquivo novamente.')
                    return redirect('emails:importar_leads')
                
                # Obter parâmetros do formulário
                nome_base = request.POST.get('nome_base')
                descricao = request.POST.get('descricao', '')
                coluna_email = request.POST.get('coluna_email')
                coluna_nome = request.POST.get('coluna_nome')
                
                if not all([nome_base, coluna_email, coluna_nome]):
                    messages.error(request, 'Nome da base, coluna de email e coluna de nome são obrigatórios')
                    return redirect('emails:importar_leads')
                
                # Reconstruir arquivo do base64
                import base64
                from django.core.files.uploadedfile import InMemoryUploadedFile
                
                arquivo_bytes = base64.b64decode(arquivo_temp['conteudo'])
                arquivo = InMemoryUploadedFile(
                    file=io.BytesIO(arquivo_bytes),
                    field_name='arquivo_csv',
                    name=arquivo_temp['nome'],
                    content_type='text/csv',
                    size=len(arquivo_bytes),
                    charset=None
                )
                
                # Importar leads
                base_leads = importar_leads_de_csv(
                    arquivo, nome_base, coluna_email, coluna_nome, descricao
                )
                
                # Limpar sessão
                del request.session['arquivo_csv_temp']
                
                messages.success(
                    request, 
                    f'Base "{nome_base}" importada com sucesso! '
                    f'{base_leads.total_validos} leads válidos, {base_leads.total_invalidos} inválidos.'
                )
                
                return redirect('emails:detalhe_base_leads', base_id=base_leads.id)
                
            except Exception as e:
                messages.error(request, f'Erro ao importar leads: {str(e)}')
                return redirect('emails:importar_leads')
    
    # GET - Mostrar formulário inicial
    context = {
        'etapa': 1,
    }
    
    return render(request, 'emails/importar_leads.html', context)


def detalhe_base_leads(request, base_id):
    """Exibe detalhes de uma base de leads"""
    
    base = get_object_or_404(BaseLeads, id=base_id)
    
    # Leads da base (paginados)
    leads = Lead.objects.filter(base_leads=base).order_by('-valido', 'linha_original')
    
    # Filtros
    valido_filter = request.GET.get('valido', '')
    search = request.GET.get('search', '')
    
    if valido_filter == 'sim':
        leads = leads.filter(valido=True)
    elif valido_filter == 'nao':
        leads = leads.filter(valido=False)
    
    if search:
        leads = leads.filter(
            Q(nome__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Paginação
    paginator = Paginator(leads, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas
    stats = {
        'total_leads': base.total_leads,
        'total_validos': base.total_validos,
        'total_invalidos': base.total_invalidos,
        'taxa_validos': base.get_taxa_validos(),
        'campanhas_usando': CampanhaEmail.objects.filter(base_leads=base).count(),
    }
    
    context = {
        'base': base,
        'page_obj': page_obj,
        'stats': stats,
        'valido_filter': valido_filter,
        'search': search,
    }
    
    return render(request, 'emails/detalhe_base_leads.html', context)


def excluir_base_leads(request, base_id):
    """Exclui uma base de leads"""
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        base = get_object_or_404(BaseLeads, id=base_id)
        
        # Verificar se há campanhas usando esta base
        campanhas_ativas = CampanhaEmail.objects.filter(
            base_leads=base,
            ativo=True,
            status__in=['agendada', 'executando']
        ).count()
        
        if campanhas_ativas > 0:
            return JsonResponse({
                'error': f'Não é possível excluir. Existem {campanhas_ativas} campanha(s) ativa(s) usando esta base.'
            }, status=400)
        
        nome_base = base.nome
        base.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Base "{nome_base}" excluída com sucesso'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def exportar_base_leads(request, base_id):
    """Exporta uma base de leads para CSV"""
    
    base = get_object_or_404(BaseLeads, id=base_id)
    
    # Criar response CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="base_leads_{base.id}_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    
    # Escrever BOM para UTF-8
    response.write('\ufeff')
    
    import csv
    writer = csv.writer(response, delimiter=';')
    
    # Cabeçalho (usar colunas originais)
    colunas_header = ['Email', 'Nome', 'Status'] + [
        col for col in base.colunas_disponiveis 
        if col not in [base.coluna_email, base.coluna_nome]
    ]
    writer.writerow(colunas_header)
    
    # Dados
    leads = Lead.objects.filter(base_leads=base).order_by('linha_original')
    
    for lead in leads:
        linha = [
            lead.email,
            lead.nome,
            'Válido' if lead.valido else f'Inválido: {lead.motivo_invalido}'
        ]
        
        # Adicionar dados adicionais
        for coluna in base.colunas_disponiveis:
            if coluna not in [base.coluna_email, base.coluna_nome]:
                linha.append(lead.dados_adicionais.get(coluna, ''))
        
        writer.writerow(linha)
    
    return response


def preview_csv_ajax(request):
    """
    API AJAX para analisar CSV e retornar sugestões de colunas
    Usado na etapa 1 da importação para dar feedback instantâneo
    """
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        arquivo = request.FILES.get('arquivo_csv')
        
        if not arquivo:
            return JsonResponse({'error': 'Nenhum arquivo enviado'}, status=400)
        
        # Analisar arquivo
        servico = ServicoImportacaoCSV()
        analise = servico.obter_sugestoes_colunas(arquivo)
        
        return JsonResponse({
            'success': True,
            'colunas': analise['colunas'],
            'sugestao_email': analise['sugestao_email'],
            'sugestao_nome': analise['sugestao_nome'],
            'preview': analise['preview'],
            'encoding': analise['encoding'],
            'delimitador': analise['delimitador'],
            'total_linhas_preview': analise['total_linhas_preview']
        })
        
    except Exception as e:
        logger.error(f'Erro ao fazer preview do CSV: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)


def validar_mapeamento_ajax(request):
    """
    API AJAX para validar mapeamento de colunas antes de importar
    """
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)
    
    try:
        # Recuperar arquivo da sessão
        arquivo_temp = request.session.get('arquivo_csv_temp')
        if not arquivo_temp:
            return JsonResponse({
                'error': 'Sessão expirou. Faça upload do arquivo novamente.'
            }, status=400)
        
        # Parâmetros
        coluna_email = request.POST.get('coluna_email')
        coluna_nome = request.POST.get('coluna_nome')
        
        if not coluna_email or not coluna_nome:
            return JsonResponse({
                'error': 'Coluna de email e nome são obrigatórias'
            }, status=400)
        
        # Reconstruir arquivo
        import base64
        from django.core.files.uploadedfile import InMemoryUploadedFile
        
        arquivo_bytes = base64.b64decode(arquivo_temp['conteudo'])
        arquivo = InMemoryUploadedFile(
            file=io.BytesIO(arquivo_bytes),
            field_name='arquivo_csv',
            name=arquivo_temp['nome'],
            content_type='text/csv',
            size=len(arquivo_bytes),
            charset=None
        )
        
        # Validar
        servico = ServicoImportacaoCSV()
        resultado = servico.validar_csv(arquivo, coluna_email, coluna_nome)
        
        return JsonResponse({
            'success': True,
            'validacao': resultado
        })
        
    except Exception as e:
        logger.error(f'Erro ao validar mapeamento: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)


# ==================== VIEWS PARA LEADS (CSV) ====================

def listar_bases_leads(request):
    """Lista todas as bases de leads importadas"""
    
    # Filtros
    search = request.GET.get('search', '')
    ativo_filter = request.GET.get('ativo', '')
    
    # Query base
    bases = BaseLeads.objects.all()
    
    # Aplicar filtros
    if search:
        bases = bases.filter(
            Q(nome__icontains=search) |
            Q(descricao__icontains=search) |
            Q(arquivo_original_nome__icontains=search)
        )
    
    if ativo_filter.lower() == 'true':
        bases = bases.filter(ativo=True)
    elif ativo_filter.lower() == 'false':
        bases = bases.filter(ativo=False)
    
    # Ordenação
    bases = bases.order_by('-data_importacao')
    
    # Paginação
    paginator = Paginator(bases, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estatísticas gerais
    stats = {
        'total_bases': BaseLeads.objects.count(),
        'bases_ativas': BaseLeads.objects.filter(ativo=True).count(),
        'total_leads': Lead.objects.filter(valido=True).count(),
        'total_leads_invalidos': Lead.objects.filter(valido=False).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'search': search,
        'ativo_filter': ativo_filter,
    }
    
    return render(request, 'emails/listar_bases_leads.html', context)


def importar_leads_csv(request):
    """View para upload e processamento inicial de CSV"""
    
    if request.method == 'POST':
        # Verificar se é mapeamento de colunas (POST com coluna_email e coluna_nome)
        if 'coluna_email' in request.POST and 'coluna_nome' in request.POST:
            # Processar mapeamento e importar
            try:
                # Obter dados da sessão
                nome = request.session.get('csv_import_nome', '')
                descricao = request.session.get('csv_import_descricao', '')
                colunas = request.session.get('csv_import_colunas', [])
                arquivo_nome = request.session.get('csv_import_arquivo_nome', 'arquivo.csv')
                arquivo_conteudo = request.session.get('csv_import_arquivo_conteudo')
                
                if not arquivo_conteudo:
                    messages.error(request, 'Dados da sessão expirados. Por favor, faça o upload novamente.')
                    return redirect('emails:importar_leads')
                
                # Obter mapeamento do formulário
                coluna_email = request.POST.get('coluna_email')
                coluna_nome = request.POST.get('coluna_nome')
                
                if not coluna_email or not coluna_nome:
                    messages.error(request, 'É necessário mapear as colunas de email e nome')
                    # Redesenhar página de mapeamento
                    context = {
                        'colunas': colunas,
                        'preview': request.session.get('csv_import_preview', []),
                        'total_linhas': request.session.get('csv_import_total_linhas', 0),
                        'arquivo_nome': arquivo_nome,
                    }
                    return render(request, 'emails/mapear_colunas_csv.html', context)
                
                # Criar arquivo temporário a partir do conteúdo da sessão
                from io import BytesIO
                arquivo = BytesIO(arquivo_conteudo)
                arquivo.name = arquivo_nome
                
                # Importar leads (com transaction.atomic para garantir atomicidade)
                try:
                    with transaction.atomic():
                        base_leads = ServicoImportacaoCSV.importar_leads(
                            arquivo=arquivo,
                            nome_base=nome or 'Base de Leads',
                            descricao=descricao,
                            coluna_email=coluna_email,
                            coluna_nome=coluna_nome
                        )
                    
                    # Limpar sessão
                    for key in ['csv_import_nome', 'csv_import_descricao', 'csv_import_colunas',
                               'csv_import_preview', 'csv_import_total_linhas', 'csv_import_arquivo_nome',
                               'csv_import_arquivo_conteudo']:
                        request.session.pop(key, None)
                    
                    messages.success(
                        request,
                        f'✅ Base de leads importada com sucesso! {base_leads.total_validos} lead(s) válido(s) importado(s). '
                        f'Linhas com problemas foram automaticamente descartadas.'
                    )
                    return redirect('emails:detalhe_base_leads', base_id=base_leads.id)
                    
                except ValidationError as e:
                    messages.error(request, str(e))
                    context = {
                        'colunas': colunas,
                        'preview': request.session.get('csv_import_preview', []),
                        'total_linhas': request.session.get('csv_import_total_linhas', 0),
                        'arquivo_nome': arquivo_nome,
                    }
                    return render(request, 'emails/mapear_colunas_csv.html', context)
                except Exception as e:
                    logger.error(f'Erro na importação: {str(e)}')
                    messages.error(request, f'Erro ao importar leads: {str(e)}')
                    return redirect('emails:importar_leads')
                    
            except Exception as e:
                logger.error(f'Erro no mapeamento: {str(e)}')
                messages.error(request, f'Erro ao processar mapeamento: {str(e)}')
                return redirect('emails:importar_leads')
        
        # POST inicial - upload do arquivo
        try:
            # Verificar se arquivo foi enviado
            if 'arquivo_csv' not in request.FILES:
                messages.error(request, 'Arquivo CSV é obrigatório')
                return redirect('emails:importar_leads')
            
            arquivo = request.FILES['arquivo_csv']
            
            # Validar extensão
            if not arquivo.name.lower().endswith('.csv'):
                messages.error(request, 'Arquivo deve ser um CSV (.csv)')
                return redirect('emails:importar_leads')
            
            # Extrair colunas do CSV
            try:
                colunas, primeira_linha, total_linhas = ServicoImportacaoCSV.extrair_colunas(arquivo)
            except Exception as e:
                messages.error(request, f'Erro ao processar arquivo CSV: {str(e)}')
                return redirect('emails:importar_leads')
            
            if not colunas:
                messages.error(request, 'Nenhuma coluna encontrada no arquivo CSV')
                return redirect('emails:importar_leads')
            
            # Obter preview dos dados
            preview = ServicoImportacaoCSV.obter_preview_dados(arquivo, limite=10)
            
            # Salvar arquivo temporariamente na sessão para processamento posterior
            # (em produção, considere usar storage temporário)
            request.session['csv_import_nome'] = request.POST.get('nome', '')
            request.session['csv_import_descricao'] = request.POST.get('descricao', '')
            request.session['csv_import_colunas'] = colunas
            request.session['csv_import_preview'] = preview
            request.session['csv_import_total_linhas'] = total_linhas
            request.session['csv_import_arquivo_nome'] = arquivo.name
            
            # Salvar arquivo em memória para próxima etapa
            arquivo.seek(0)
            arquivo_content = arquivo.read()
            request.session['csv_import_arquivo_conteudo'] = arquivo_content
            
            context = {
                'colunas': colunas,
                'preview': preview,
                'total_linhas': total_linhas,
                'arquivo_nome': arquivo.name,
            }
            
            return render(request, 'emails/mapear_colunas_csv.html', context)
            
        except Exception as e:
            logger.error(f'Erro na importação de CSV: {str(e)}')
            messages.error(request, f'Erro ao processar arquivo: {str(e)}')
            return redirect('emails:importar_leads')
    
    # GET - mostrar formulário de upload
    return render(request, 'emails/importar_leads.html')




def detalhe_base_leads(request, base_id):
    """Detalhes de uma base de leads"""
    
    base = get_object_or_404(BaseLeads, id=base_id)
    
    # Leads válidos e inválidos
    leads_validos = Lead.objects.filter(base_leads=base, valido=True).order_by('linha_original')
    leads_invalidos = Lead.objects.filter(base_leads=base, valido=False).order_by('linha_original')
    
    # Paginação
    paginator_validos = Paginator(leads_validos, 50)
    page_validos = request.GET.get('page_validos', 1)
    page_obj_validos = paginator_validos.get_page(page_validos)
    
    paginator_invalidos = Paginator(leads_invalidos, 50)
    page_invalidos = request.GET.get('page_invalidos', 1)
    page_obj_invalidos = paginator_invalidos.get_page(page_invalidos)
    
    # Campanhas que usam esta base
    campanhas = CampanhaEmail.objects.filter(base_leads=base)
    
    context = {
        'base': base,
        'page_obj_validos': page_obj_validos,
        'page_obj_invalidos': page_obj_invalidos,
        'campanhas': campanhas,
    }
    
    return render(request, 'emails/detalhe_base_leads.html', context)


def excluir_base_leads(request, base_id):
    """Exclui uma base de leads"""
    
    base = get_object_or_404(BaseLeads, id=base_id)
    
    if request.method == 'POST':
        try:
            nome_base = base.nome
            base.delete()
            messages.success(request, f'Base de leads "{nome_base}" excluída com sucesso!')
            return redirect('emails:listar_bases_leads')
        except Exception as e:
            logger.error(f'Erro ao excluir base: {str(e)}')
            messages.error(request, f'Erro ao excluir base: {str(e)}')
            return redirect('emails:detalhe_base_leads', base_id=base_id)
    
    context = {
        'base': base,
    }
    
    return render(request, 'emails/excluir_base_leads.html', context)


def exportar_base_leads(request, base_id):
    """Exporta uma base de leads para CSV"""
    
    base = get_object_or_404(BaseLeads, id=base_id)
    
    # Buscar apenas leads válidos
    leads = Lead.objects.filter(base_leads=base, valido=True).order_by('linha_original')
    
    # Criar resposta HTTP com CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="base_leads_{base.id}_{base.nome}.csv"'
    
    # Escrever CSV
    import csv
    writer = csv.writer(response, delimiter=';')
    
    # Cabeçalho
    cabecalho = [base.coluna_nome, base.coluna_email]
    for coluna in base.colunas_disponiveis:
        if coluna not in [base.coluna_nome, base.coluna_email]:
            cabecalho.append(coluna)
    writer.writerow(cabecalho)
    
    # Dados
    for lead in leads:
        linha = [lead.nome, lead.email]
        for coluna in base.colunas_disponiveis:
            if coluna not in [base.coluna_nome, base.coluna_email]:
                linha.append(lead.dados_adicionais.get(coluna, ''))
        writer.writerow(linha)
    
    return response
