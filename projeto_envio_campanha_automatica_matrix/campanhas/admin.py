from django.contrib import admin
from django import forms
from .models import (
    TemplateSQL, VariavelTemplate, CredenciaisHubsoft, ClienteConsultado, 
    ConsultaExecucao, ConsultaCliente, CredenciaisBancoDados, MatrixAPIConfig, 
    HSMTemplate, EnvioHSMMatrix, EnvioHSMIndividual, ConfiguracaoPagamentoHSM
)

@admin.register(CredenciaisBancoDados)
class CredenciaisBancoDadosAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo_banco', 'host', 'banco', 'ativo', 'data_criacao')
    list_filter = ('tipo_banco', 'ativo')
    search_fields = ('titulo', 'host', 'banco', 'usuario')
    readonly_fields = ('data_criacao', 'data_atualizacao')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'tipo_banco', 'ativo')
        }),
        ('Conexão', {
            'fields': ('host', 'porta', 'banco')
        }),
        ('Credenciais', {
            'fields': ('usuario', 'senha')
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

class VariavelTemplateForm(forms.ModelForm):
    opcoes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4, 
            'cols': 50,
            'placeholder': 'Uma opção por linha:\nOpção 1\nOpção 2\nOpção 3'
        }),
        required=False,
        help_text='Para tipo "Lista de Opções": digite uma opção por linha'
    )
    
    class Meta:
        model = VariavelTemplate
        fields = ['nome', 'label', 'tipo', 'obrigatorio', 'valor_padrao', 'opcoes', 'ordem', 'ativo']

class VariavelTemplateInline(admin.TabularInline):
    model = VariavelTemplate
    form = VariavelTemplateForm
    extra = 0
    fields = ['nome', 'label', 'tipo', 'obrigatorio', 'valor_padrao', 'opcoes', 'ordem', 'ativo']
    ordering = ['ordem', 'nome']
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('ordem', 'nome')

class TemplateSQLForm(forms.ModelForm):
    variaveis_config = forms.JSONField(
        widget=forms.Textarea(attrs={
            'rows': 6, 
            'cols': 80, 
            'style': 'font-family: monospace; font-size: 12px;'
        }),
        help_text='⚠️ LEGADO: Use a seção "Variáveis" abaixo para uma interface mais amigável. Este campo JSON é mantido para compatibilidade.',
        required=False
    )
    
    class Meta:
        model = TemplateSQL
        fields = '__all__'

@admin.register(TemplateSQL)
class TemplateSQLAdmin(admin.ModelAdmin):
    form = TemplateSQLForm
    inlines = [VariavelTemplateInline]
    list_display = ('titulo', 'ativo', 'get_variaveis_count', 'get_variaveis_detectadas_count', 'data_criacao', 'data_atualizacao')
    list_filter = ('ativo',)
    search_fields = ('titulo', 'descricao')
    readonly_fields = ('data_criacao', 'data_atualizacao', 'get_variaveis_detectadas')
    actions = ['sincronizar_variaveis_acao', 'debug_deteccao_variaveis']
    
    def get_variaveis_count(self, obj):
        """Exibe quantas variáveis estão configuradas"""
        return obj.variaveis.filter(ativo=True).count()
    get_variaveis_count.short_description = 'Variáveis Configuradas'
    
    def get_variaveis_detectadas_count(self, obj):
        """Exibe quantas variáveis foram detectadas no SQL"""
        return len(obj.extrair_variaveis_do_sql())
    get_variaveis_detectadas_count.short_description = 'Variáveis no SQL'
    
    def get_variaveis_detectadas(self, obj):
        """Mostra as variáveis detectadas automaticamente no SQL"""
        variaveis = obj.extrair_variaveis_do_sql()
        if variaveis:
            return ', '.join(variaveis)
        return 'Nenhuma variável detectada'
    get_variaveis_detectadas.short_description = 'Variáveis Detectadas no SQL'
    
    def sincronizar_variaveis_acao(self, request, queryset):
        """Ação para sincronizar variáveis automaticamente"""
        count = 0
        for template in queryset:
            template.sincronizar_variaveis_com_sql()
            count += 1
        
        self.message_user(
            request,
            f'{count} template(s) sincronizado(s) com sucesso. '
            'Variáveis foram criadas/atualizadas conforme encontradas no SQL.'
        )
    sincronizar_variaveis_acao.short_description = 'Sincronizar variáveis com SQL'
    
    def debug_deteccao_variaveis(self, request, queryset):
        """Ação para fazer debug da detecção de variáveis"""
        import json
        from django.contrib import messages
        
        for template in queryset:
            debug_info = template.debug_extrair_variaveis()
            
            # Formata a mensagem de debug
            if 'erro' in debug_info:
                self.message_user(
                    request,
                    f'❌ {template.titulo}: {debug_info["erro"]}',
                    level=messages.ERROR
                )
            else:
                variaveis = ', '.join(debug_info['variaveis_encontradas']) if debug_info['variaveis_encontradas'] else 'Nenhuma'
                self.message_user(
                    request,
                    f'🔍 {template.titulo}: Encontradas {debug_info["total_variaveis_unicas"]} variáveis: {variaveis}',
                    level=messages.INFO
                )
                
                # Debug detalhado no log do Django
                print(f"\n🔍 DEBUG - Template: {template.titulo}")
                print(f"SQL Preview: {debug_info['sql_preview']}")
                print(f"Variáveis encontradas: {debug_info['variaveis_encontradas']}")
                for pattern_name, info in debug_info['patterns_tested'].items():
                    print(f"  {pattern_name}: {info['count']} matches - {info['matches']}")
    
    debug_deteccao_variaveis.short_description = '🔍 Debug: detectar variáveis'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'descricao', 'ativo')
        }),
        ('Consulta SQL', {
            'fields': ('consulta_sql',),
            'description': '💡 Use {{nome_variavel}} para definir variáveis dinâmicas. Exemplo: WHERE data = \'{{data_vencimento}}\'. Após salvar, use a ação "Sincronizar variáveis" para criar automaticamente os campos de variáveis.'
        }),
        ('Detecção Automática', {
            'fields': ('get_variaveis_detectadas',),
            'description': '🔍 Variáveis detectadas automaticamente no SQL acima'
        }),
        ('Sistema Legado (JSON)', {
            'fields': ('variaveis_config',),
            'classes': ('collapse',),
            'description': '⚠️ Campo mantido para compatibilidade. Use a seção "Variáveis" abaixo para uma interface mais amigável.'
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

@admin.register(CredenciaisHubsoft)
class CredenciaisHubsoftAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'username', 'ativo', 'data_criacao', 'data_atualizacao')
    list_filter = ('ativo',)
    search_fields = ('titulo', 'username')
    readonly_fields = ('data_criacao', 'data_atualizacao')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'ativo')
        }),
        ('Credenciais', {
            'fields': ('client_id', 'client_secret', 'username', 'password')
        }),
        ('URLs', {
            'fields': ('url_base', 'url_token')
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ClienteConsultado)
class ClienteConsultadoAdmin(admin.ModelAdmin):
    list_display = ('codigo_cliente', 'nome_razaosocial', 'get_empresa', 'telefone_corrigido', 'data_criacao')
    list_filter = ('credencial_banco', 'data_criacao')
    search_fields = ('codigo_cliente', 'nome_razaosocial', 'telefone_corrigido')
    readonly_fields = ('data_criacao', 'data_atualizacao')
    
    def get_empresa(self, obj):
        """Exibe o nome da empresa/base"""
        if obj.credencial_banco:
            return obj.credencial_banco.titulo
        return "Não definida"
    get_empresa.short_description = 'Empresa/Base'
    get_empresa.admin_order_field = 'credencial_banco__titulo'
    
    fieldsets = (
        ('Informações do Cliente', {
            'fields': ('codigo_cliente', 'nome_razaosocial', 'telefone_corrigido', 'credencial_banco'),
            'description': 'Dados básicos do cliente e identificação da empresa/base'
        }),
        ('Informações da Fatura', {
            'fields': ('id_fatura', 'vencimento_fatura', 'valor_fatura')
        }),
        ('Informações de Pagamento', {
            'fields': ('pix', 'codigo_barras', 'link_boleto')
        }),
        ('Dados Dinâmicos', {
            'fields': ('dados_dinamicos',),
            'classes': ('collapse',),
            'description': 'Dados adicionais do cliente que podem ser usados em HSM e Flow'
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

class ConsultaExecucaoForm(forms.ModelForm):
    class Meta:
        model = ConsultaExecucao
        fields = '__all__'
        widgets = {
            'pular_consulta_api': forms.CheckboxInput(attrs={
                'onchange': 'toggleCredencialHubsoft(this)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Torna credencial_hubsoft não obrigatória no formulário
        self.fields['credencial_hubsoft'].required = False
        
        # Adiciona help text dinâmico
        if self.instance and self.instance.pular_consulta_api:
            self.fields['credencial_hubsoft'].help_text = "Não é necessária quando 'Pular Consulta na API' está marcado"
        else:
            self.fields['credencial_hubsoft'].help_text = "Obrigatória para consultas na API"

    def clean(self):
        cleaned_data = super().clean()
        pular_api = cleaned_data.get('pular_consulta_api')
        credencial_hubsoft = cleaned_data.get('credencial_hubsoft')
        
        # Se não pular API, credencial é obrigatória
        if not pular_api and not credencial_hubsoft:
            raise forms.ValidationError({
                'credencial_hubsoft': 'Credencial Hubsoft é obrigatória quando a consulta da API está habilitada.'
            })
        
        return cleaned_data

@admin.register(ConsultaExecucao)
class ConsultaExecucaoAdmin(admin.ModelAdmin):
    form = ConsultaExecucaoForm
    list_display = ('titulo', 'template_sql', 'pular_consulta_api', 'status', 'total_registros_sql', 'total_consultados_api', 'total_erros', 'data_inicio', 'data_fim')
    list_filter = ('status', 'pular_consulta_api', 'template_sql', 'credencial_hubsoft')
    search_fields = ('titulo',)
    readonly_fields = ('data_inicio', 'data_fim', 'total_registros_sql', 'total_consultados_api', 'total_erros', 'get_variaveis_utilizadas', 'get_sql_processado')
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'template_sql')
        }),
        ('Configurações da API', {
            'fields': ('pular_consulta_api', 'credencial_hubsoft'),
            'description': 'Configure se deseja consultar a API para dados financeiros. Se "Pular Consulta na API" estiver marcado, a credencial Hubsoft não é necessária.'
        }),
        ('Credenciais do Banco', {
            'fields': ('credencial_banco',)
        }),
        ('Variáveis', {
            'fields': ('valores_variaveis',),
            'classes': ('collapse',)
        }),
        ('Status e Resultados', {
            'fields': ('status', 'total_registros_sql', 'total_consultados_api', 'total_erros'),
            'classes': ('collapse',)
        }),
        ('Dados Técnicos', {
            'fields': ('get_variaveis_utilizadas', 'get_sql_processado', 'log_execucao'),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('data_inicio', 'data_fim'),
            'classes': ('collapse',)
        }),
    )
    
    class Media:
        js = ('admin/js/consulta_execucao.js',)
    
    def get_variaveis_utilizadas(self, obj):
        """Exibe as variáveis e valores utilizados na execução"""
        if obj.valores_variaveis:
            items = []
            for var, valor in obj.valores_variaveis.items():
                items.append(f"{var}: {valor}")
            return '; '.join(items)
        return 'Nenhuma variável utilizada'
    get_variaveis_utilizadas.short_description = 'Variáveis Utilizadas'
    
    def get_sql_processado(self, obj):
        """Mostra o SQL processado com as variáveis substituídas"""
        if obj.valores_variaveis and obj.template_sql:
            try:
                sql_processado = obj.template_sql.substituir_variaveis(obj.valores_variaveis)
                # Limita o tamanho para exibição
                if len(sql_processado) > 1000:
                    return sql_processado[:1000] + '...\n\n[SQL truncado para exibição]'
                return sql_processado
            except Exception as e:
                return f"Erro ao processar SQL: {str(e)}"
        return 'Sem variáveis para processar'
    get_sql_processado.short_description = 'SQL Processado (com variáveis substituídas)'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'template_sql', 'credencial_hubsoft', 'credencial_banco', 'status')
        }),
        ('Parâmetros da Execução', {
            'fields': ('get_variaveis_utilizadas', 'valores_variaveis', 'get_sql_processado'),
            'description': 'Variáveis e valores utilizados nesta execução'
        }),
        ('Estatísticas', {
            'fields': ('total_registros_sql', 'total_consultados_api', 'total_erros')
        }),
        ('Logs', {
            'fields': ('log_execucao',)
        }),
        ('Datas', {
            'fields': ('data_inicio', 'data_fim')
        }),
    )

@admin.register(ConsultaCliente)
class ConsultaClienteAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'execucao', 'sucesso_api', 'data_consulta')
    list_filter = ('sucesso_api', 'execucao')
    search_fields = ('cliente__nome_razaosocial', 'cliente__codigo_cliente')
    readonly_fields = ('data_consulta',)
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('execucao', 'cliente', 'sucesso_api')
        }),
        ('Dados', {
            'fields': ('dados_originais_sql', 'dados_api_response')
        }),
        ('Erro', {
            'fields': ('erro_api',)
        }),
        ('Datas', {
            'fields': ('data_consulta',)
        }),
    )

@admin.register(MatrixAPIConfig)
class MatrixAPIConfigAdmin(admin.ModelAdmin):
    list_display = ('nome', 'base_url', 'cod_conta', 'ativo', 'data_criacao')
    list_filter = ('ativo',)
    search_fields = ('nome', 'base_url')
    readonly_fields = ('data_criacao', 'data_atualizacao')
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'ativo')
        }),
        ('Configurações da API', {
            'fields': ('base_url', 'api_key', 'cod_conta')
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

@admin.register(HSMTemplate)
class HSMTemplateAdmin(admin.ModelAdmin):
    list_display = ('nome', 'hsm_id', 'tipo_template', 'tipo_envio', 'cod_flow', 'ativo', 'data_criacao')
    list_filter = ('tipo_template', 'tipo_envio', 'ativo')
    search_fields = ('nome', 'descricao')
    readonly_fields = ('data_criacao', 'data_atualizacao')
    
    def get_tipo_envio_display(self, obj):
        return dict(HSMTemplate.TIPO_ENVIO_CHOICES).get(obj.tipo_envio, obj.tipo_envio)
    get_tipo_envio_display.short_description = 'Tipo de Envio'
    
    def get_tipo_template_display(self, obj):
        return dict(HSMTemplate.TIPO_TEMPLATE_CHOICES).get(obj.tipo_template, obj.tipo_template)
    get_tipo_template_display.short_description = 'Tipo de Template'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'tipo_template', 'ativo')
        }),
        ('Configurações HSM', {
            'fields': ('hsm_id', 'cod_flow', 'tipo_envio')
        }),
        ('Variáveis', {
            'fields': ('variaveis_descricao',),
            'description': 'Descrição das variáveis do HSM em formato JSON'
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ConfiguracaoPagamentoHSM)
class ConfiguracaoPagamentoHSMAdmin(admin.ModelAdmin):
    list_display = ('nome', 'razao_social_empresa', 'cnpj_empresa', 'tipo_produto', 'ativo', 'data_criacao')
    list_filter = ('tipo_produto', 'ativo', 'data_criacao')
    search_fields = ('nome', 'razao_social_empresa', 'cnpj_empresa', 'nome_produto_padrao')
    readonly_fields = ('data_criacao', 'data_atualizacao')
    actions = ['ativar_configuracoes', 'desativar_configuracoes']
    
    def ativar_configuracoes(self, request, queryset):
        """Ação para ativar configurações"""
        count = queryset.update(ativo=True)
        self.message_user(
            request,
            f'{count} configuração(ões) ativada(s) com sucesso.'
        )
    ativar_configuracoes.short_description = '✅ Ativar configurações selecionadas'
    
    def desativar_configuracoes(self, request, queryset):
        """Ação para desativar configurações"""
        count = queryset.update(ativo=False)
        self.message_user(
            request,
            f'{count} configuração(ões) desativada(s) com sucesso.'
        )
    desativar_configuracoes.short_description = '❌ Desativar configurações selecionadas'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'ativo')
        }),
        ('Dados da Empresa', {
            'fields': ('razao_social_empresa', 'cnpj_empresa'),
            'description': 'Informações da empresa para PIX e documentos'
        }),
        ('Dados do Produto', {
            'fields': ('nome_produto_padrao', 'tipo_produto'),
            'description': 'Configurações padrão do produto'
        }),
        ('Valores Padrão', {
            'fields': ('val_imposto', 'val_desconto'),
            'description': 'Valores padrão para impostos e descontos'
        }),
        ('Variáveis do Flow', {
            'fields': ('variaveis_flow_padrao',),
            'description': 'Variáveis adicionais que serão enviadas para o flow (formato JSON)',
            'classes': ('collapse',)
        }),
        ('Configurações Extras', {
            'fields': ('configuracao_extra',),
            'description': 'Configurações adicionais em formato JSON',
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )

# =============================================================================
# ADMIN PARA ENVIO HSM MATRIX
# =============================================================================

class EnvioHSMIndividualInline(admin.TabularInline):
    model = EnvioHSMIndividual
    extra = 0
    readonly_fields = ('cliente', 'status', 'template_usado', 'data_envio', 'tentativas')
    fields = ('cliente', 'status', 'template_usado', 'data_envio', 'tentativas')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(EnvioHSMMatrix)
class EnvioHSMMatrixAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'get_tipo_template', 'hsm_template', 'matrix_api_config', 'status_envio', 'get_progresso', 'total_clientes', 'ativo', 'data_criacao')
    list_filter = ('status_envio', 'hsm_template__tipo_template', 'hsm_template', 'matrix_api_config', 'ativo')
    search_fields = ('titulo', 'hsm_template__nome', 'matrix_api_config__nome', 'razao_social_empresa', 'cnpj_empresa')
    readonly_fields = ('data_criacao', 'data_inicio_envio', 'data_fim_envio', 'get_progresso', 'get_duracao', 'get_tipo_template')
    actions = ['calcular_totais_acao', 'iniciar_envio_acao', 'pausar_envio_acao', 'cancelar_envio_acao']
    inlines = [EnvioHSMIndividualInline]
    
    def get_progresso(self, obj):
        """Exibe o progresso do envio com percentual"""
        if obj.total_clientes == 0:
            return "0% (0/0)"
        percentual = obj.get_progresso_percentual()
        return f"{percentual}% ({obj.total_enviados + obj.total_erros}/{obj.total_clientes})"
    get_progresso.short_description = 'Progresso'
    
    def get_duracao(self, obj):
        """Calcula e exibe a duração do envio"""
        if obj.data_inicio_envio and obj.data_fim_envio:
            duracao = obj.data_fim_envio - obj.data_inicio_envio
            return f"{duracao}"
        elif obj.data_inicio_envio:
            from django.utils import timezone
            duracao = timezone.now() - obj.data_inicio_envio
            return f"{duracao} (em andamento)"
        return "Não iniciado"
    get_duracao.short_description = 'Duração'
    
    def get_tipo_template(self, obj):
        """Exibe o tipo do template HSM"""
        if obj.hsm_template:
            tipo_dict = dict(obj.hsm_template.TIPO_TEMPLATE_CHOICES)
            tipo = tipo_dict.get(obj.hsm_template.tipo_template, obj.hsm_template.tipo_template)
            # Adiciona emoji para facilitar identificação
            if obj.hsm_template.tipo_template == 'pagamento':
                return f"💳 {tipo}"
            else:
                return f"📄 {tipo}"
        return "Não definido"
    get_tipo_template.short_description = 'Tipo'
    get_tipo_template.admin_order_field = 'hsm_template__tipo_template'
    
    def calcular_totais_acao(self, request, queryset):
        """Ação para recalcular totais"""
        count = 0
        for envio in queryset:
            envio.calcular_totais()
            count += 1
        
        self.message_user(
            request,
            f'{count} envio(s) com totais recalculados com sucesso.'
        )
    calcular_totais_acao.short_description = '🔄 Recalcular totais'
    
    def iniciar_envio_acao(self, request, queryset):
        """Ação para iniciar envio"""
        from django.contrib import messages
        count = 0
        for envio in queryset:
            if envio.pode_iniciar():
                envio.atualizar_status('enviando', 'Envio iniciado via admin')
                count += 1
            else:
                self.message_user(
                    request,
                    f'❌ Envio "{envio.titulo}" não pode ser iniciado. Verifique se está ativo e tem dados válidos.',
                    level=messages.WARNING
                )
        
        if count > 0:
            self.message_user(
                request,
                f'{count} envio(s) iniciado(s) com sucesso.'
            )
    iniciar_envio_acao.short_description = '▶️ Iniciar envio'
    
    def pausar_envio_acao(self, request, queryset):
        """Ação para pausar envio"""
        count = 0
        for envio in queryset:
            if envio.status_envio == 'enviando':
                envio.atualizar_status('pausado', 'Envio pausado via admin')
                count += 1
        
        if count > 0:
            self.message_user(
                request,
                f'{count} envio(s) pausado(s) com sucesso.'
            )
    pausar_envio_acao.short_description = '⏸️ Pausar envio'
    
    def cancelar_envio_acao(self, request, queryset):
        """Ação para cancelar envio"""
        count = 0
        for envio in queryset:
            if envio.status_envio in ['pendente', 'enviando', 'pausado']:
                envio.atualizar_status('cancelado', 'Envio cancelado via admin')
                count += 1
        
        if count > 0:
            self.message_user(
                request,
                f'{count} envio(s) cancelado(s) com sucesso.'
            )
    cancelar_envio_acao.short_description = '❌ Cancelar envio'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('titulo', 'get_tipo_template', 'ativo'),
            'description': 'Informações básicas do envio HSM'
        }),
        ('Configurações', {
            'fields': ('hsm_template', 'hsm_template_contingencia', 'matrix_api_config', 'consulta_execucao')
        }),
        ('Configurações do Segundo HSM', {
            'fields': ('habilitar_segundo_hsm', 'hsm_template_segundo', 'configuracao_variaveis_segundo', 'intervalo_segundo_hsm'),
            'classes': ('collapse',),
            'description': 'Configurações para envio duplo de HSM'
        }),
        ('Status e Progresso', {
            'fields': ('status_envio', 'get_progresso', 'get_duracao')
        }),
        ('Estatísticas', {
            'fields': ('total_clientes', 'total_enviados', 'total_erros', 'total_pendentes')
        }),
        ('Configurações de Pagamento', {
            'fields': ('configuracao_pagamento_hsm', 'razao_social_empresa', 'cnpj_empresa', 'nome_produto_padrao', 'configuracao_pagamento'),
            'classes': ('collapse',),
            'description': 'Configurações específicas para templates de pagamento HSM. Use uma configuração salva ou preencha manualmente.'
        }),
        ('Configurações de Pagamento - Segundo HSM', {
            'fields': ('razao_social_empresa_segundo', 'cnpj_empresa_segundo', 'nome_produto_padrao_segundo', 'configuracao_pagamento_segundo'),
            'classes': ('collapse',),
            'description': 'Configurações específicas para o segundo HSM de pagamento (quando habilitado)'
        }),
        ('Configurações Avançadas', {
            'fields': ('configuracao_variaveis', 'configuracao_variaveis_contingencia', 'filtros_adicionais'),
            'classes': ('collapse',),
            'description': 'Configurações avançadas para mapeamento de variáveis e filtros'
        }),
        ('Logs', {
            'fields': ('log_execucao',),
            'classes': ('collapse',)
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_inicio_envio', 'data_fim_envio'),
            'classes': ('collapse',)
        }),
    )

@admin.register(EnvioHSMIndividual)
class EnvioHSMIndividualAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'envio_matrix', 'get_tipo_template', 'status', 'template_usado', 'hsm_enviado', 'ativo', 'get_flow_variaveis_count', 'data_envio', 'tentativas')
    list_filter = ('status', 'template_usado', 'hsm_enviado', 'ativo', 'envio_matrix__hsm_template__tipo_template', 'envio_matrix', 'data_envio')
    search_fields = ('cliente__nome_razaosocial', 'cliente__codigo_cliente', 'envio_matrix__titulo')
    readonly_fields = ('data_envio', 'tentativas', 'get_resposta_api_formatada', 'get_dados_pagamento_formatados', 'get_tipo_template', 'get_flow_variaveis_formatadas')
    
    def get_tipo_template(self, obj):
        """Exibe o tipo do template HSM"""
        if obj.envio_matrix and obj.envio_matrix.hsm_template:
            tipo_dict = dict(obj.envio_matrix.hsm_template.TIPO_TEMPLATE_CHOICES)
            tipo = tipo_dict.get(obj.envio_matrix.hsm_template.tipo_template, obj.envio_matrix.hsm_template.tipo_template)
            # Adiciona emoji para facilitar identificação
            if obj.envio_matrix.hsm_template.tipo_template == 'pagamento':
                return f"💳 {tipo}"
            else:
                return f"📄 {tipo}"
        return "Não definido"
    get_tipo_template.short_description = 'Tipo'
    get_tipo_template.admin_order_field = 'envio_matrix__hsm_template__tipo_template'
    
    def get_resposta_api_formatada(self, obj):
        """Formata a resposta da API para exibição"""
        if obj.resposta_api:
            import json
            return json.dumps(obj.resposta_api, indent=2, ensure_ascii=False)
        return 'Nenhuma resposta'
    get_resposta_api_formatada.short_description = 'Resposta da API (formatada)'
    
    def get_dados_pagamento_formatados(self, obj):
        """Formata os dados de pagamento para exibição"""
        if obj.dados_pagamento:
            import json
            return json.dumps(obj.dados_pagamento, indent=2, ensure_ascii=False)
        return 'Nenhum dado de pagamento'
    get_dados_pagamento_formatados.short_description = 'Dados de Pagamento (formatados)'
    
    def get_flow_variaveis_formatadas(self, obj):
        """Formata as variáveis do flow que foram enviadas para exibição"""
        if hasattr(obj, 'flow_variaveis_enviadas') and obj.flow_variaveis_enviadas:
            import json
            return json.dumps(obj.flow_variaveis_enviadas, indent=2, ensure_ascii=False)
        return 'Nenhuma variável do flow enviada'
    get_flow_variaveis_formatadas.short_description = 'Variáveis do Flow Enviadas (formatadas)'
    
    def get_flow_variaveis_count(self, obj):
        """Exibe quantas variáveis do flow foram enviadas"""
        if hasattr(obj, 'flow_variaveis_enviadas') and obj.flow_variaveis_enviadas:
            count = len(obj.flow_variaveis_enviadas)
            return f"📊 {count} vars"
        return "📊 0 vars"
    get_flow_variaveis_count.short_description = 'Flow Vars'
    get_flow_variaveis_count.admin_order_field = 'flow_variaveis_enviadas'
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('envio_matrix', 'cliente', 'status', 'template_usado', 'get_tipo_template', 'hsm_enviado', 'ativo')
        }),
        ('Detalhes do Envio', {
            'fields': ('data_envio', 'tentativas', 'variaveis_utilizadas', 'envio_relacionado')
        }),
        ('Variáveis do Flow Enviadas', {
            'fields': ('get_flow_variaveis_formatadas', 'flow_variaveis_enviadas'),
            'classes': ('collapse',),
            'description': 'Variáveis que foram enviadas para o flow no momento do envio'
        }),
        ('Dados de Pagamento', {
            'fields': ('url_file', 'get_dados_pagamento_formatados', 'dados_pagamento'),
            'classes': ('collapse',),
            'description': 'Dados específicos para envios de HSM de pagamento'
        }),
        ('Resposta da API', {
            'fields': ('get_resposta_api_formatada', 'resposta_api'),
            'classes': ('collapse',)
        }),
        ('Erro', {
            'fields': ('erro_detalhado',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
