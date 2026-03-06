from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import (
    ConsultaExecucao, ConsultaCliente, ClienteConsultado,
    TemplateSQL, CredenciaisBancoDados, CredenciaisHubsoft,
    EnvioHSMMatrix, HSMTemplate, MatrixAPIConfig, EnvioHSMIndividual,
    ConfiguracaoPagamentoHSM
)


class CredenciaisBancoDadosSerializer(serializers.ModelSerializer):
    """Serializer para credenciais de banco de dados"""
    class Meta:
        model = CredenciaisBancoDados
        fields = ['id', 'titulo', 'tipo_banco', 'host', 'porta', 'banco', 'ativo']


class CredenciaisHubsoftSerializer(serializers.ModelSerializer):
    """Serializer para credenciais Hubsoft"""
    class Meta:
        model = CredenciaisHubsoft
        fields = ['id', 'titulo', 'url_base', 'username', 'ativo', 'data_criacao']


class TemplateSQLSerializer(serializers.ModelSerializer):
    """Serializer para template SQL"""
    class Meta:
        model = TemplateSQL
        fields = ['id', 'titulo', 'descricao', 'consulta_sql', 'ativo', 'data_criacao']


class ClienteConsultadoSerializer(serializers.ModelSerializer):
    """Serializer para cliente consultado"""
    class Meta:
        model = ClienteConsultado
        fields = [
            'id', 'codigo_cliente', 'nome_razaosocial', 'telefone_corrigido',
            'vencimento_fatura', 'valor_fatura', 'pix', 'codigo_barras', 'link_boleto',
            'id_fatura', 'data_criacao', 'data_atualizacao'
        ]


class ConsultaClienteSerializer(serializers.ModelSerializer):
    """Serializer para consulta de cliente"""
    cliente = ClienteConsultadoSerializer(read_only=True)
    template_sql_variaveis = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ConsultaCliente
        fields = [
            'id', 'cliente', 'dados_originais_sql', 'dados_api_response',
            'sucesso_api', 'erro_api', 'data_consulta', 'template_sql_variaveis'
        ]
    
    def get_template_sql_variaveis(self, obj):
        """Retorna as variáveis do template SQL e os valores fornecidos"""
        if not obj.execucao or not obj.execucao.template_sql:
            return None
        
        template_sql = obj.execucao.template_sql
        variaveis_config = template_sql.get_variaveis_configuradas()
        valores_fornecidos = obj.execucao.valores_variaveis or {}
        
        # Formatar variáveis com informações completas
        variaveis_formatadas = []
        for var_name, config in variaveis_config.items():
            variaveis_formatadas.append({
                'nome': var_name,
                'label': config.get('label', var_name.replace('_', ' ').title()),
                'tipo': config.get('tipo', 'text'),
                'obrigatorio': config.get('obrigatorio', True),
                'valor_padrao': config.get('valor_padrao', ''),
                'valor_fornecido': valores_fornecidos.get(var_name, config.get('valor_padrao', '')),
                'opcoes': config.get('opcoes', '').split('\n') if config.get('opcoes') else []
            })
        
        return {
            'template_id': template_sql.id,
            'template_titulo': template_sql.titulo,
            'variaveis': variaveis_formatadas,
            'valores_fornecidos': valores_fornecidos
        }


class ConsultaExecucaoDetailSerializer(serializers.ModelSerializer):
    """Serializer detalhado para consulta de execução"""
    template_sql = TemplateSQLSerializer(read_only=True)
    credencial_banco = CredenciaisBancoDadosSerializer(read_only=True)
    credencial_hubsoft = CredenciaisHubsoftSerializer(read_only=True)
    consultas_clientes = ConsultaClienteSerializer(source='consultacliente_set', many=True, read_only=True)
    
    # Propriedades calculadas
    clientes_processados = serializers.ReadOnlyField()
    clientes_com_sucesso = serializers.ReadOnlyField()
    clientes_com_erro = serializers.ReadOnlyField()
    
    class Meta:
        model = ConsultaExecucao
        fields = [
            'id', 'titulo', 'status', 'total_registros_sql', 'total_consultados_api',
            'total_erros', 'log_execucao', 'data_inicio', 'data_fim', 'pular_consulta_api',
            'valores_variaveis', 'template_sql', 'credencial_banco', 'credencial_hubsoft',
            'consultas_clientes', 'clientes_processados', 'clientes_com_sucesso', 'clientes_com_erro'
        ]


class ConsultaExecucaoListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listagem de execuções"""
    template_sql_titulo = serializers.CharField(source='template_sql.titulo', read_only=True)
    credencial_banco_titulo = serializers.CharField(source='credencial_banco.titulo', read_only=True)
    
    # Propriedades calculadas
    clientes_processados = serializers.ReadOnlyField()
    clientes_com_sucesso = serializers.ReadOnlyField()
    clientes_com_erro = serializers.ReadOnlyField()
    
    class Meta:
        model = ConsultaExecucao
        fields = [
            'id', 'titulo', 'status', 'total_registros_sql', 'total_consultados_api',
            'total_erros', 'data_inicio', 'data_fim', 'template_sql_titulo',
            'credencial_banco_titulo', 'clientes_processados', 'clientes_com_sucesso', 'clientes_com_erro'
        ]


class ConsultaExecucaoCreateSerializer(serializers.ModelSerializer):
    """Serializer para criar nova execução de consulta"""
    # Campos de entrada
    template_sql_id = serializers.IntegerField(write_only=True)
    credencial_banco_id = serializers.IntegerField(write_only=True)
    credencial_hubsoft_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    valores_variaveis = serializers.JSONField(required=False, default=dict)
    pular_consulta_api = serializers.BooleanField(default=False)
    iniciar_processamento = serializers.BooleanField(default=True, write_only=True)
    
    # Campos de saída
    redirect_url = serializers.CharField(read_only=True)
    
    class Meta:
        model = ConsultaExecucao
        fields = [
            'titulo', 'template_sql_id', 'credencial_banco_id', 'credencial_hubsoft_id',
            'valores_variaveis', 'pular_consulta_api', 'iniciar_processamento',
            'id', 'status', 'data_inicio', 'redirect_url'
        ]
        extra_kwargs = {
            'titulo': {'required': True},
        }
    
    def validate(self, data):
        """Validações customizadas"""
        # Validar se template SQL existe
        try:
            template_sql = TemplateSQL.objects.get(id=data['template_sql_id'])
        except TemplateSQL.DoesNotExist:
            raise serializers.ValidationError("Template SQL não encontrado.")
        
        # Validar se credencial de banco existe
        try:
            CredenciaisBancoDados.objects.get(id=data['credencial_banco_id'])
        except CredenciaisBancoDados.DoesNotExist:
            raise serializers.ValidationError("Credencial de banco de dados não encontrada.")
        
        # Validar credencial Hubsoft se API não for pulada
        if not data.get('pular_consulta_api', False):
            credencial_hubsoft_id = data.get('credencial_hubsoft_id')
            if not credencial_hubsoft_id:
                raise serializers.ValidationError(
                    "Credencial Hubsoft é obrigatória quando a consulta da API está habilitada."
                )
            try:
                CredenciaisHubsoft.objects.get(id=credencial_hubsoft_id)
            except CredenciaisHubsoft.DoesNotExist:
                raise serializers.ValidationError("Credencial Hubsoft não encontrada.")
        
        # Validar variáveis do template
        variaveis_config = template_sql.get_variaveis_configuradas()
        valores_variaveis = data.get('valores_variaveis', {})
        
        for var_name, config in variaveis_config.items():
            valor = valores_variaveis.get(var_name)
            
            if config.get('obrigatorio', True) and not valor:
                raise serializers.ValidationError(
                    f'A variável "{config.get("label", var_name)}" é obrigatória.'
                )
            
            # Usar valor padrão se não fornecido e não obrigatório
            if not valor and not config.get('obrigatorio', True):
                valores_variaveis[var_name] = config.get('valor_padrao', '')
        
        data['valores_variaveis'] = valores_variaveis
        return data
    
    def create(self, validated_data):
        """Criar nova execução"""
        import threading
        from django.urls import reverse
        from .views import processar_consulta_completa
        
        # Remover campos que não pertencem ao modelo
        iniciar_processamento = validated_data.pop('iniciar_processamento', True)
        
        # Ajustar campos para o modelo
        validated_data['template_sql_id'] = validated_data.pop('template_sql_id')
        validated_data['credencial_banco_id'] = validated_data.pop('credencial_banco_id')
        
        # Credencial Hubsoft é opcional se API for pulada
        credencial_hubsoft_id = validated_data.pop('credencial_hubsoft_id', None)
        if not validated_data.get('pular_consulta_api', False):
            validated_data['credencial_hubsoft_id'] = credencial_hubsoft_id
        
        # Definir status inicial
        validated_data['status'] = 'pendente'
        
        # Criar execução
        execucao = super().create(validated_data)
        
        # Iniciar processamento se solicitado
        if iniciar_processamento:
            thread = threading.Thread(target=processar_consulta_completa, args=(execucao.id,))
            thread.daemon = True
            thread.start()
        
        # Adicionar URL de redirect (caminho absoluto, sem usar reverse)
        # Não podemos usar reverse() aqui porque a URL web tem namespace 'campanhas',
        # mas estamos em um contexto de API (sem namespace)
        execucao.redirect_url = f'/whatsapp/execucao/{execucao.id}/'
        
        return execucao


# =============================================================================
# SERIALIZERS PARA HSM
# =============================================================================

class MatrixAPIConfigSerializer(serializers.ModelSerializer):
    """Serializer para configurações da API Matrix"""
    class Meta:
        model = MatrixAPIConfig
        fields = ['id', 'nome', 'base_url', 'cod_conta', 'ativo', 'data_criacao', 'data_atualizacao']
        extra_kwargs = {
            'api_key': {'write_only': True},  # Não exibir em listagem
        }
    
    def to_representation(self, instance):
        """Personaliza a representação baseada na ação"""
        data = super().to_representation(instance)
        
        # Se for listagem, ocultar informações sensíveis
        if self.context.get('view') and self.context['view'].action == 'list':
            pass  # Manter apenas campos seguros
        else:
            # Para detalhes, incluir api_key (mas mascarada)
            data['api_key'] = f"{instance.api_key[:8]}..." if instance.api_key else None
        
        return data


class MatrixAPIConfigDetailSerializer(serializers.ModelSerializer):
    """Serializer detalhado para configurações da API Matrix (inclui api_key)"""
    class Meta:
        model = MatrixAPIConfig
        fields = '__all__'


class HSMTemplateSerializer(serializers.ModelSerializer):
    """Serializer para templates HSM"""
    class Meta:
        model = HSMTemplate
        fields = [
            'id', 'nome', 'hsm_id', 'cod_flow', 'tipo_envio', 'tipo_template',
            'descricao', 'variaveis_descricao', 'ativo', 'data_criacao', 'data_atualizacao'
        ]
    
    def to_representation(self, instance):
        """Personaliza a representação"""
        data = super().to_representation(instance)
        
        # Converter choices para texto legível
        data['tipo_envio_display'] = instance.get_tipo_envio_display()
        data['tipo_template_display'] = instance.get_tipo_template_display()
        
        return data


class EnvioHSMIndividualSerializer(serializers.ModelSerializer):
    """Serializer para envios individuais de HSM"""
    cliente_nome = serializers.CharField(source='cliente.nome_razaosocial', read_only=True)
    cliente_telefone = serializers.CharField(source='cliente.telefone_corrigido', read_only=True)
    
    class Meta:
        model = EnvioHSMIndividual
        fields = [
            'id', 'cliente_nome', 'cliente_telefone', 'status', 'data_envio',
            'template_usado', 'hsm_enviado', 'erro_detalhado'
        ]


class EnvioHSMMatrixListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listagem de envios HSM"""
    hsm_template_nome = serializers.CharField(source='hsm_template.nome', read_only=True)
    matrix_config_nome = serializers.CharField(source='matrix_api_config.nome', read_only=True)
    execucao_titulo = serializers.CharField(source='consulta_execucao.titulo', read_only=True)
    
    # Propriedades calculadas
    progresso_percentual = serializers.SerializerMethodField()
    
    class Meta:
        model = EnvioHSMMatrix
        fields = [
            'id', 'titulo', 'status_envio', 'total_clientes', 'total_enviados',
            'total_erros', 'total_pendentes', 'data_criacao', 'data_inicio_envio',
            'data_fim_envio', 'hsm_template_nome', 'matrix_config_nome',
            'execucao_titulo', 'progresso_percentual'
        ]
    
    def get_progresso_percentual(self, obj):
        """Calcula o progresso percentual do envio"""
        if obj.total_clientes > 0:
            processados = obj.total_enviados + obj.total_erros
            return round((processados / obj.total_clientes) * 100, 2)
        return 0.0


class ConfiguracaoPagamentoHSMSerializer(serializers.ModelSerializer):
    """Serializer para configurações de pagamento HSM"""
    
    class Meta:
        model = ConfiguracaoPagamentoHSM
        fields = [
            'id', 'nome', 'descricao', 'razao_social_empresa', 'cnpj_empresa',
            'nome_produto_padrao', 'tipo_produto', 'val_imposto', 'val_desconto',
            'variaveis_flow_padrao', 'configuracao_extra', 'ativo',
            'data_criacao', 'data_atualizacao'
        ]
        read_only_fields = ['id', 'data_criacao', 'data_atualizacao']


class EnvioHSMMatrixDetailSerializer(serializers.ModelSerializer):
    """Serializer detalhado para envios HSM"""
    hsm_template = HSMTemplateSerializer(read_only=True)
    matrix_api_config = MatrixAPIConfigSerializer(read_only=True)
    configuracao_pagamento_hsm = ConfiguracaoPagamentoHSMSerializer(read_only=True)
    
    # Propriedades calculadas
    progresso_percentual = serializers.SerializerMethodField()
    
    class Meta:
        model = EnvioHSMMatrix
        fields = [
            'id', 'titulo', 'hsm_template', 'matrix_api_config', 'status_envio',
            'data_criacao', 'data_inicio_envio', 'data_fim_envio',
            'total_clientes', 'total_enviados', 'total_erros', 'total_pendentes',
            'log_execucao', 'configuracao_variaveis',
            'progresso_percentual', 'configuracao_pagamento_hsm',
            # Campos de configuração manual de pagamento
            'razao_social_empresa', 'cnpj_empresa', 'nome_produto_padrao', 'configuracao_pagamento'
        ]
    
    def get_progresso_percentual(self, obj):
        """Calcula o progresso percentual do envio"""
        if obj.total_clientes > 0:
            processados = obj.total_enviados + obj.total_erros
            return round((processados / obj.total_clientes) * 100, 2)
        return 0.0


class EnvioHSMMatrixCreateSerializer(serializers.ModelSerializer):
    """Serializer para criar novos envios HSM"""
    # Campos de entrada
    execucao_id = serializers.IntegerField(write_only=True)
    hsm_template_id = serializers.IntegerField(write_only=True)
    matrix_config_id = serializers.IntegerField(write_only=True)
    iniciar_processamento = serializers.BooleanField(default=True, write_only=True)
    
    # Campos opcionais para configuração de pagamento
    configuracao_pagamento_hsm_id = serializers.IntegerField(write_only=True, required=False)
    
    # Campos de saída
    redirect_url = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = EnvioHSMMatrix
        fields = [
            'titulo', 'execucao_id', 'hsm_template_id', 'matrix_config_id',
            'configuracao_variaveis', 'iniciar_processamento', 'configuracao_pagamento_hsm_id',
            # Campos de configuração de pagamento manual
            'razao_social_empresa', 'cnpj_empresa', 'nome_produto_padrao', 'configuracao_pagamento',
            # Campos de saída
            'id', 'status_envio', 'data_criacao', 'redirect_url'
        ]
        extra_kwargs = {
            'titulo': {'required': True},
            'razao_social_empresa': {'required': False},
            'cnpj_empresa': {'required': False},
            'nome_produto_padrao': {'required': False},
            'configuracao_pagamento': {'required': False},
        }
    
    def validate(self, data):
        """Validações customizadas"""
        # Validar se execução existe e está concluída
        try:
            execucao = ConsultaExecucao.objects.get(id=data['execucao_id'])
            if execucao.status != 'concluida':
                raise serializers.ValidationError(
                    f"A execução deve estar com status 'concluída'. Status atual: {execucao.status}"
                )
        except ConsultaExecucao.DoesNotExist:
            raise serializers.ValidationError("Execução não encontrada.")
        
        # Validar se template HSM existe e está ativo
        try:
            template = HSMTemplate.objects.get(id=data['hsm_template_id'])
            if not template.ativo:
                raise serializers.ValidationError("Template HSM deve estar ativo.")
        except HSMTemplate.DoesNotExist:
            raise serializers.ValidationError("Template HSM não encontrado.")
        
        # Validar se configuração Matrix existe e está ativa
        try:
            config = MatrixAPIConfig.objects.get(id=data['matrix_config_id'])
            if not config.ativo:
                raise serializers.ValidationError("Configuração Matrix deve estar ativa.")
        except MatrixAPIConfig.DoesNotExist:
            raise serializers.ValidationError("Configuração Matrix não encontrada.")
        
        # Validar mapeamento de variáveis
        configuracao_variaveis = data.get('configuracao_variaveis', {})
        variaveis_template = template.get_variaveis_descricao()
        
        for var_id, var_config in variaveis_template.items():
            # Verificar se var_config é string ou dict
            if isinstance(var_config, str):
                # Formato simples: {"1": "nome_cliente"} - todas são obrigatórias por padrão
                obrigatorio = True
                nome_variavel = var_config
            else:
                # Formato complexo: {"1": {"nome": "nome_cliente", "obrigatorio": true}}
                obrigatorio = var_config.get('obrigatorio', True)
                nome_variavel = var_config.get('nome', var_id)
            
            if obrigatorio:
                if var_id not in configuracao_variaveis:
                    raise serializers.ValidationError(
                        f'A variável "{nome_variavel}" é obrigatória e deve estar mapeada.'
                    )
        
        # Validar se os campos mapeados existem no modelo ClienteConsultado ou são campos virtuais
        campos_validos = [
            # Campos do modelo ClienteConsultado
            'codigo_cliente', 'nome_razaosocial', 'telefone_corrigido',
            'vencimento_fatura', 'valor_fatura', 'pix', 'codigo_barras',
            'link_boleto', 'id_fatura',
            # Campos virtuais criados pela função mapear_campos_cliente_para_hsm
            'nome_cliente', 'telefone', 'pix_copia_cola', 'empresa'
        ]
        
        # Normalizar configuracao_variaveis para formato simples
        configuracao_normalizada = {}
        for var_id, mapeamento in configuracao_variaveis.items():
            if isinstance(mapeamento, dict):
                # Formato complexo: {"campo_cliente": "nome_razaosocial", "obrigatorio": true}
                campo_mapeado = mapeamento.get('campo_cliente')
            else:
                # Formato simples: "nome_razaosocial"
                campo_mapeado = mapeamento
            
            if campo_mapeado:
                configuracao_normalizada[var_id] = campo_mapeado
                
                # Validar se o campo existe
                if campo_mapeado not in campos_validos:
                    raise serializers.ValidationError(
                        f'Campo "{campo_mapeado}" não é válido para mapeamento. '
                        f'Campos válidos: {", ".join(campos_validos)}'
                    )
        
        # Atualizar data com configuração normalizada
        data['configuracao_variaveis'] = configuracao_normalizada
        
        # Validação de configuração de pagamento
        hsm_template = data.get('hsm_template_id')
        if hsm_template:
            template = HSMTemplate.objects.get(id=hsm_template)
            if template.tipo_template == 'pagamento':
                config_pagamento_id = data.get('configuracao_pagamento_hsm_id')
                razao_social = data.get('razao_social_empresa')
                cnpj = data.get('cnpj_empresa')
                nome_produto = data.get('nome_produto_padrao')

                if not config_pagamento_id and not (razao_social and cnpj and nome_produto):
                    raise serializers.ValidationError(
                        "Para templates de pagamento, é necessário fornecer 'configuracao_pagamento_hsm_id' "
                        "ou preencher 'razao_social_empresa', 'cnpj_empresa' e 'nome_produto_padrao'."
                    )
                if config_pagamento_id:
                    try:
                        ConfiguracaoPagamentoHSM.objects.get(id=config_pagamento_id)
                    except ConfiguracaoPagamentoHSM.DoesNotExist:
                        raise serializers.ValidationError(f"Configuração de Pagamento HSM com ID {config_pagamento_id} não encontrada.")
        
        return data
    
    def get_redirect_url(self, obj):
        """Retorna URL de redirect para o envio criado"""
        # Retorna caminho absoluto sem usar reverse()
        return f'/whatsapp/envios-hsm/{obj.id}/'
    
    def create(self, validated_data):
        """Criar novo envio HSM"""
        import threading
        from django.urls import reverse
        from .views import processar_envio_hsm_background
        
        # Remover campos que não pertencem ao modelo
        iniciar_processamento = validated_data.pop('iniciar_processamento', True)
        execucao_id = validated_data.pop('execucao_id')
        hsm_template_id = validated_data.pop('hsm_template_id')
        matrix_config_id = validated_data.pop('matrix_config_id')
        configuracao_pagamento_hsm_id = validated_data.pop('configuracao_pagamento_hsm_id', None)
        
        # Ajustar campos para o modelo
        validated_data['consulta_execucao_id'] = execucao_id
        validated_data['hsm_template_id'] = hsm_template_id
        validated_data['matrix_api_config_id'] = matrix_config_id
        
        # Configurar configuração de pagamento se fornecida
        if configuracao_pagamento_hsm_id:
            try:
                from .models import ConfiguracaoPagamentoHSM
                config_pagamento = ConfiguracaoPagamentoHSM.objects.get(id=configuracao_pagamento_hsm_id)
                validated_data['configuracao_pagamento_hsm'] = config_pagamento
                
                # ✅ CORREÇÃO: Copiar dados da configuração para campos manuais (como faz a aplicação web)
                if not validated_data.get('razao_social_empresa'):
                    validated_data['razao_social_empresa'] = config_pagamento.razao_social_empresa
                if not validated_data.get('cnpj_empresa'):
                    validated_data['cnpj_empresa'] = config_pagamento.cnpj_empresa
                if not validated_data.get('nome_produto_padrao'):
                    validated_data['nome_produto_padrao'] = config_pagamento.nome_produto_padrao
                    
            except ConfiguracaoPagamentoHSM.DoesNotExist:
                raise serializers.ValidationError("Configuração de pagamento não encontrada.")
        
        # Definir status inicial
        validated_data['status_envio'] = 'pendente'
        
        # Calcular total de clientes da execução
        execucao = ConsultaExecucao.objects.get(id=execucao_id)
        validated_data['total_clientes'] = execucao.clientes_processados
        
        # Criar envio
        envio = super().create(validated_data)
        
        # Iniciar processamento se solicitado
        if iniciar_processamento:
            thread = threading.Thread(target=processar_envio_hsm_background, args=(envio.id,))
            thread.daemon = True
            thread.start()
        
        return envio
