from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.contrib.admin import helpers
from .models import (
    ConfiguracaoServidorEmail, 
    TemplateEmail, 
    CampanhaEmail, 
    EnvioEmailIndividual, 
    LogEnvioEmail,
    BaseLeads,
    Lead
)


@admin.register(ConfiguracaoServidorEmail)
class ConfiguracaoServidorEmailAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'servidor_smtp', 'porta', 'email_remetente', 
        'ativo', 'status_conexao', 'data_ultimo_teste'
    ]
    list_filter = ['ativo', 'usar_tls', 'usar_ssl', 'data_criacao']
    search_fields = ['nome', 'servidor_smtp', 'email_remetente', 'usuario']
    readonly_fields = ['data_criacao', 'data_atualizacao', 'data_ultimo_teste', 'resultado_ultimo_teste']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'ativo')
        }),
        ('Configuração SMTP', {
            'fields': ('servidor_smtp', 'porta', 'usuario', 'senha', 'usar_tls', 'usar_ssl', 'timeout')
        }),
        ('Remetente', {
            'fields': ('email_remetente', 'nome_remetente')
        }),
        ('Teste de Conexão', {
            'fields': ('data_ultimo_teste', 'resultado_ultimo_teste'),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['testar_conexoes_selecionadas', 'delete_selected']
    
    def status_conexao(self, obj):
        if obj.data_ultimo_teste:
            if obj.resultado_ultimo_teste and 'sucesso' in obj.resultado_ultimo_teste.lower():
                return format_html(
                    '<span style="color: green;">✓ Conectado</span>'
                )
            else:
                return format_html(
                    '<span style="color: red;">✗ Erro</span>'
                )
        return format_html('<span style="color: orange;">? Não testado</span>')
    
    status_conexao.short_description = 'Status da Conexão'
    
    def testar_conexoes_selecionadas(self, request, queryset):
        """Ação para testar conexões SMTP selecionadas"""
        sucessos = 0
        erros = 0
        
        for config in queryset:
            sucesso, mensagem = config.testar_conexao()
            if sucesso:
                sucessos += 1
            else:
                erros += 1
        
        if sucessos > 0:
            messages.success(request, '{} conexão(ões) testada(s) com sucesso.'.format(sucessos))
        if erros > 0:
            messages.error(request, '{} conexão(ões) falharam no teste.'.format(erros))
    
    testar_conexoes_selecionadas.short_description = "Testar conexões SMTP selecionadas"
    
    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(TemplateEmail)
class TemplateEmailAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'tipo', 'ativo', 'total_enviados', 
        'taxa_sucesso_display', 'data_ultimo_envio'
    ]
    list_filter = ['tipo', 'ativo', 'data_criacao']
    search_fields = ['nome', 'assunto', 'descricao']
    readonly_fields = [
        'total_enviados', 'total_sucessos', 'total_erros', 
        'data_criacao', 'data_atualizacao', 'data_ultimo_envio',
        'variaveis_detectadas_display'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'tipo', 'ativo', 'descricao')
        }),
        ('Conteúdo do Email', {
            'fields': ('assunto', 'corpo_html', 'corpo_texto')
        }),
        ('Personalização', {
            'fields': ('css_personalizado', 'variaveis_personalizadas'),
            'classes': ('collapse',)
        }),
        ('Variáveis Detectadas', {
            'fields': ('variaveis_detectadas_display',),
            'classes': ('collapse',)
        }),
        ('Estatísticas', {
            'fields': ('total_enviados', 'total_sucessos', 'total_erros'),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao', 'data_ultimo_envio'),
            'classes': ('collapse',)
        }),
    )
    
    def taxa_sucesso_display(self, obj):
        taxa = obj.get_taxa_sucesso()
        if taxa >= 90:
            color = 'green'
        elif taxa >= 70:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{}</span>',
            color, '{:.1f}%'.format(taxa)
        )
    
    taxa_sucesso_display.short_description = 'Taxa de Sucesso'
    
    def variaveis_detectadas_display(self, obj):
        variaveis = obj.extrair_variaveis_do_template()
        if variaveis:
            html = '<ul>'
            for var in variaveis:
                html += '<li><code>{{' + var + '}}</code></li>'
            html += '</ul>'
            return mark_safe(html)
        return 'Nenhuma variável detectada'
    
    variaveis_detectadas_display.short_description = 'Variáveis Detectadas no Template'
    
    # Habilitar exclusão
    actions = ['delete_selected']
    
    def has_delete_permission(self, request, obj=None):
        return True


class EnvioEmailIndividualInline(admin.TabularInline):
    model = EnvioEmailIndividual
    extra = 0
    readonly_fields = [
        'cliente', 'email_destinatario', 'nome_destinatario', 
        'status', 'data_envio', 'tentativas', 'erro_detalhado'
    ]
    can_delete = True
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CampanhaEmail)
class CampanhaEmailAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'status', 'tipo_agendamento', 'template_email',
        'progresso_display', 'taxa_sucesso_display', 'proxima_execucao'
    ]
    list_filter = [
        'status', 'tipo_agendamento', 'ativo', 'template_email__tipo', 'data_criacao'
    ]
    search_fields = ['nome', 'descricao', 'template_email__nome']
    readonly_fields = [
        'total_destinatarios', 'total_enviados', 'total_sucessos', 
        'total_erros', 'total_pendentes', 'data_criacao', 'data_atualizacao',
        'data_inicio_execucao', 'data_fim_execucao', 'proxima_execucao'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'ativo', 'status')
        }),
        ('Configuração', {
            'fields': ('template_email', 'configuracao_servidor')
        }),
        ('Dados dos Clientes', {
            'fields': ('template_sql', 'consulta_execucao'),
            'description': 'Configure como os dados dos clientes serão obtidos'
        }),
        ('Agendamento', {
            'fields': (
                'tipo_agendamento', 'data_agendamento', 'expressao_cron',
                'intervalo_recorrencia', 'data_fim_recorrencia'
            ),
            'description': 'Configure quando e como a campanha será executada'
        }),
        ('Configurações Avançadas', {
            'fields': (
                'limite_envios_por_execucao', 'intervalo_entre_envios',
                'filtros_sql_adicionais'
            ),
            'classes': ('collapse',)
        }),
        ('Estatísticas', {
            'fields': (
                'total_destinatarios', 'total_enviados', 'total_sucessos',
                'total_erros', 'total_pendentes'
            ),
            'classes': ('collapse',)
        }),
        ('Controle de Execução', {
            'fields': (
                'data_inicio_execucao', 'data_fim_execucao', 
                'proxima_execucao', 'log_execucao'
            ),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [EnvioEmailIndividualInline]
    actions = ['iniciar_campanhas', 'pausar_campanhas', 'cancelar_campanhas']
    
    def progresso_display(self, obj):
        progresso = obj.get_progresso_percentual()
        
        if obj.status == 'concluida':
            color = 'green'
        elif obj.status == 'executando':
            color = 'blue'
        elif obj.status == 'erro':
            color = 'red'
        else:
            color = 'gray'
        
        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; color: white; line-height: 20px;">'
            '{}</div></div>',
            progresso, color, '{:.1f}%'.format(progresso)
        )
    
    progresso_display.short_description = 'Progresso'
    
    def taxa_sucesso_display(self, obj):
        taxa = obj.get_taxa_sucesso()
        if taxa >= 90:
            color = 'green'
        elif taxa >= 70:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{}</span>',
            color, '{:.1f}%'.format(taxa)
        )
    
    taxa_sucesso_display.short_description = 'Taxa de Sucesso'
    
    def iniciar_campanhas(self, request, queryset):
        """Ação para iniciar campanhas selecionadas"""
        count = 0
        for campanha in queryset:
            if campanha.pode_executar():
                campanha.atualizar_status('agendada', 'Campanha iniciada manualmente pelo admin')
                count += 1
        
        if count > 0:
            messages.success(request, '{} campanha(s) iniciada(s) com sucesso.'.format(count))
        else:
            messages.warning(request, 'Nenhuma campanha pôde ser iniciada. Verifique as condições.')
    
    iniciar_campanhas.short_description = "Iniciar campanhas selecionadas"
    
    def pausar_campanhas(self, request, queryset):
        """Ação para pausar campanhas selecionadas"""
        count = queryset.filter(status__in=['agendada', 'executando']).update(status='pausada')
        if count > 0:
            messages.success(request, '{} campanha(s) pausada(s) com sucesso.'.format(count))
    
    pausar_campanhas.short_description = "Pausar campanhas selecionadas"
    
    def cancelar_campanhas(self, request, queryset):
        """Ação para cancelar campanhas selecionadas"""
        count = queryset.exclude(status__in=['concluida', 'cancelada']).update(status='cancelada')
        if count > 0:
            messages.success(request, '{} campanha(s) cancelada(s) com sucesso.'.format(count))
    
    cancelar_campanhas.short_description = "Cancelar campanhas selecionadas"
    
    # Habilitar exclusão
    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(EnvioEmailIndividual)
class EnvioEmailIndividualAdmin(admin.ModelAdmin):
    list_display = [
        'nome_destinatario', 'email_destinatario', 'campanha',
        'status', 'data_envio', 'tentativas'
    ]
    list_filter = ['status', 'campanha', 'data_envio', 'tentativas']
    search_fields = [
        'nome_destinatario', 'email_destinatario', 
        'campanha__nome', 'cliente__nome_razaosocial'
    ]
    readonly_fields = [
        'campanha', 'cliente', 'email_destinatario', 'nome_destinatario',
        'assunto_enviado', 'corpo_enviado', 'variaveis_utilizadas',
        'anexos_enviados', 'data_envio', 'tempo_envio_ms',
        'resposta_servidor', 'message_id'
    ]
    
    fieldsets = (
        ('Informações do Envio', {
            'fields': ('campanha', 'cliente', 'status', 'tentativas')
        }),
        ('Destinatário', {
            'fields': ('nome_destinatario', 'email_destinatario')
        }),
        ('Conteúdo Enviado', {
            'fields': ('assunto_enviado', 'corpo_enviado'),
            'classes': ('collapse',)
        }),
        ('Dados Técnicos', {
            'fields': (
                'variaveis_utilizadas', 'anexos_enviados', 'data_envio',
                'tempo_envio_ms', 'resposta_servidor', 'message_id'
            ),
            'classes': ('collapse',)
        }),
        ('Erro', {
            'fields': ('erro_detalhado',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return True

    # Adicionar ação de exclusão em massa
    actions = ['delete_selected', 'limpar_envios_antigos']
    
    def limpar_envios_antigos(self, request, queryset):
        """Remove envios individuais antigos (mais de 30 dias)"""
        from django.utils import timezone
        from datetime import timedelta
        
        data_limite = timezone.now() - timedelta(days=30)
        count = EnvioEmailIndividual.objects.filter(
            data_envio__lt=data_limite
        ).delete()[0]
        
        if count > 0:
            messages.success(request, f'{count} envios antigos removidos com sucesso.')
        else:
            messages.info(request, 'Nenhum envio antigo encontrado para remoção.')
    
    limpar_envios_antigos.short_description = "Limpar envios antigos (30+ dias)"


@admin.register(LogEnvioEmail)
class LogEnvioEmailAdmin(admin.ModelAdmin):
    list_display = ['nivel', 'acao', 'campanha', 'data_criacao', 'mensagem_resumo']
    list_filter = ['nivel', 'acao', 'data_criacao']
    search_fields = ['acao', 'mensagem', 'campanha__nome']
    readonly_fields = ['campanha', 'envio_individual', 'nivel', 'acao', 'mensagem', 'dados_extras', 'data_criacao']
    
    fieldsets = (
        ('Informações do Log', {
            'fields': ('nivel', 'acao', 'data_criacao')
        }),
        ('Contexto', {
            'fields': ('campanha', 'envio_individual')
        }),
        ('Detalhes', {
            'fields': ('mensagem', 'dados_extras'),
            'classes': ('collapse',)
        }),
    )
    
    def mensagem_resumo(self, obj):
        if len(obj.mensagem) > 100:
            return obj.mensagem[:100] + '...'
        return obj.mensagem
    
    mensagem_resumo.short_description = 'Mensagem'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return True

    # Adicionar ação de exclusão em massa
    actions = ['delete_selected', 'limpar_logs_antigos']
    
    def limpar_logs_antigos(self, request, queryset):
        """Remove logs antigos (mais de 60 dias)"""
        from django.utils import timezone
        from datetime import timedelta
        
        data_limite = timezone.now() - timedelta(days=60)
        count = LogEnvioEmail.objects.filter(
            data_criacao__lt=data_limite
        ).delete()[0]
        
        if count > 0:
            messages.success(request, f'{count} logs antigos removidos com sucesso.')
        else:
            messages.info(request, 'Nenhum log antigo encontrado para remoção.')
    
    limpar_logs_antigos.short_description = "Limpar logs antigos (60+ dias)"


@admin.register(BaseLeads)
class BaseLeadsAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'total_leads', 'total_validos', 'total_invalidos',
        'ativo', 'data_importacao', 'arquivo_original_nome'
    ]
    list_filter = ['ativo', 'data_importacao']
    search_fields = ['nome', 'descricao', 'arquivo_original_nome']
    readonly_fields = [
        'total_leads', 'total_validos', 'total_invalidos',
        'data_importacao', 'colunas_disponiveis', 'coluna_email', 'coluna_nome'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'ativo')
        }),
        ('Arquivo', {
            'fields': ('arquivo_original_nome',)
        }),
        ('Mapeamento de Colunas', {
            'fields': ('coluna_email', 'coluna_nome', 'colunas_disponiveis')
        }),
        ('Estatísticas', {
            'fields': ('total_leads', 'total_validos', 'total_invalidos')
        }),
        ('Data', {
            'fields': ('data_importacao',)
        }),
    )
    
    actions = ['delete_selected']
    
    def has_delete_permission(self, request, obj=None):
        return True


class LeadInline(admin.TabularInline):
    model = Lead
    extra = 0
    readonly_fields = ['email', 'nome', 'linha_original', 'valido', 'motivo_invalido', 'dados_adicionais']
    can_delete = True
    
    fields = ['linha_original', 'nome', 'email', 'valido', 'motivo_invalido', 'dados_adicionais']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        'nome', 'email', 'base_leads', 'valido', 'linha_original', 'data_criacao'
    ]
    list_filter = ['valido', 'base_leads', 'data_criacao']
    search_fields = ['nome', 'email', 'base_leads__nome']
    readonly_fields = ['base_leads', 'email', 'nome', 'linha_original', 'valido', 'motivo_invalido', 'dados_adicionais', 'data_criacao']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('base_leads', 'nome', 'email', 'valido')
        }),
        ('Dados do CSV', {
            'fields': ('linha_original', 'dados_adicionais')
        }),
        ('Validação', {
            'fields': ('motivo_invalido',)
        }),
        ('Data', {
            'fields': ('data_criacao',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return True
    
    actions = ['delete_selected']


# Adicionar inline de leads ao BaseLeadsAdmin
BaseLeadsAdmin.inlines = [LeadInline]


# Customização do admin site
admin.site.site_header = "Sistema de Envio de Emails"
admin.site.site_title = "Emails Admin"
admin.site.index_title = "Administração do Sistema de Emails"