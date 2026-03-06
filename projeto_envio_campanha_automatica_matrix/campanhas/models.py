# models.py (versão melhorada)
from django.db import models
from django.core.exceptions import ValidationError
import json
from django.utils import timezone

class TemplateSQL(models.Model):
    TIPO_VARIAVEL_CHOICES = [
        ('text', 'Texto'),
        ('number', 'Número'),
        ('date', 'Data'),
        ('datetime', 'Data e Hora'),
        ('select', 'Lista de Opções'),
    ]
    
    consulta_sql = models.TextField(verbose_name="Consulta SQL")
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    variaveis_config = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name="Configuração das Variáveis",
        help_text="Configuração das variáveis no formato: {'var_name': {'tipo': 'text', 'label': 'Label', 'obrigatorio': True, 'valor_padrao': '', 'opcoes': []}}"
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Atualização")

    class Meta:
        verbose_name = "Template SQL"
        verbose_name_plural = "Templates SQL"

    def __str__(self):
        return self.titulo
    
    def extrair_variaveis_do_sql(self):
        """
        Extrai variáveis do SQL no formato {{variavel}}
        Retorna uma lista de nomes de variáveis encontradas
        """
        import re
        
        if not self.consulta_sql:
            return []
        
        # Múltiplos padrões para capturar diferentes formatos
        patterns = [
            # Padrão principal: {{variavel}}
            r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}',
            # Padrão com espaços: {{ variavel }}
            r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}',
            # Padrão relaxado: {{variavel1}} ou {{variavel_teste}}
            r'\{\{([a-zA-Z_][a-zA-Z0-9_\-]*)\}\}',
        ]
        
        variaveis = set()
        
        for pattern in patterns:
            matches = re.findall(pattern, self.consulta_sql, re.IGNORECASE)
            variaveis.update(matches)
        
        # Remove variáveis vazias e limpa espaços
        variaveis = {var.strip() for var in variaveis if var.strip()}
        
        return sorted(list(variaveis))  # Remove duplicatas e ordena
    
    def debug_extrair_variaveis(self):
        """
        Método de debug para testar a extração de variáveis
        Retorna informações detalhadas sobre a detecção
        """
        import re
        
        if not self.consulta_sql:
            return {'erro': 'SQL vazio'}
        
        patterns = [
            ('Padrão principal', r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}'),
            ('Padrão com espaços', r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'),
            ('Padrão relaxado', r'\{\{([a-zA-Z_][a-zA-Z0-9_\-]*)\}\}'),
        ]
        
        resultado = {
            'sql_preview': self.consulta_sql[:200] + '...' if len(self.consulta_sql) > 200 else self.consulta_sql,
            'patterns_tested': {},
            'variaveis_encontradas': []
        }
        
        todas_variaveis = set()
        
        for nome, pattern in patterns:
            matches = re.findall(pattern, self.consulta_sql, re.IGNORECASE)
            resultado['patterns_tested'][nome] = {
                'pattern': pattern,
                'matches': matches,
                'count': len(matches)
            }
            todas_variaveis.update(matches)
        
        # Remove variáveis vazias e limpa espaços
        todas_variaveis = {var.strip() for var in todas_variaveis if var.strip()}
        resultado['variaveis_encontradas'] = sorted(list(todas_variaveis))
        resultado['total_variaveis_unicas'] = len(todas_variaveis)
        
        return resultado
    
    def get_variaveis_configuradas(self):
        """
        Retorna as variáveis configuradas, priorizando o novo sistema de modelos
        sobre o JSON legado
        """
        # Primeiro tenta usar as variáveis do novo modelo
        variaveis_modelo = self.variaveis.filter(ativo=True)
        if variaveis_modelo.exists():
            config = {}
            for var in variaveis_modelo:
                config[var.nome] = var.to_config_dict()
            return config
        
        # Fallback para o sistema JSON legado
        if not self.variaveis_config:
            self.variaveis_config = {}
        
        variaveis_sql = self.extrair_variaveis_do_sql()
        
        # Para cada variável encontrada no SQL, cria uma configuração padrão se não existir
        for var in variaveis_sql:
            if var not in self.variaveis_config:
                self.variaveis_config[var] = {
                    'tipo': 'text',
                    'label': var.replace('_', ' ').title(),
                    'obrigatorio': True,
                    'valor_padrao': '',
                    'opcoes': []
                }
        
        return self.variaveis_config
    
    def sincronizar_variaveis_com_sql(self):
        """
        Sincroniza as variáveis do modelo com as encontradas no SQL
        Cria variáveis faltantes e marca como inativas as que não estão mais no SQL
        """
        variaveis_sql = set(self.extrair_variaveis_do_sql())
        variaveis_existentes = set(self.variaveis.values_list('nome', flat=True))
        
        # Criar variáveis que estão no SQL mas não no modelo
        variaveis_para_criar = variaveis_sql - variaveis_existentes
        for var_nome in variaveis_para_criar:
            VariavelTemplate.objects.create(
                template_sql=self,
                nome=var_nome,
                label=var_nome.replace('_', ' ').title(),
                tipo='text',
                obrigatorio=True,
                ordem=self.variaveis.count()
            )
        
        # Marcar como inativas as variáveis que não estão mais no SQL
        variaveis_para_desativar = variaveis_existentes - variaveis_sql
        self.variaveis.filter(nome__in=variaveis_para_desativar).update(ativo=False)
        
        # Reativar variáveis que voltaram ao SQL
        variaveis_para_reativar = variaveis_sql & variaveis_existentes
        self.variaveis.filter(nome__in=variaveis_para_reativar).update(ativo=True)
    
    def substituir_variaveis(self, valores_variaveis):
        """
        Substitui as variáveis no SQL pelos valores fornecidos
        Suporta múltiplos formatos de placeholder e formatação automática de datas
        """
        import re
        import logging
        from datetime import datetime
        
        logger = logging.getLogger(__name__)
        
        if not valores_variaveis:
            logger.info("Nenhuma variável para substituir")
            return self.consulta_sql
        
        sql_processado = self.consulta_sql
        logger.info(f"SQL original tem {len(sql_processado)} caracteres")
        logger.info(f"Variáveis para substituir: {valores_variaveis}")
        
        # DEBUG: Prints diretos para garantir visibilidade
        print(f"🔧 SUBSTITUIR_VARIAVEIS - Template: {self.titulo}")
        print(f"🔧 Variáveis recebidas: {valores_variaveis}")
        print(f"🔧 SQL original (últimas 100 chars): ...{sql_processado[-100:]}")
        
        # Processar e formatar variáveis
        valores_formatados = {}
        for var_name, valor in valores_variaveis.items():
            valor_formatado = self._formatar_variavel(var_name, valor)
            valores_formatados[var_name] = valor_formatado
            
            if valor_formatado != str(valor):
                print(f"📅 FORMATAÇÃO: {var_name} = '{valor}' → '{valor_formatado}'")
        
        for var_name, valor_formatado in valores_formatados.items():
            # Múltiplos padrões para substituição
            patterns = [
                # Padrão exato: {{variavel}}
                f"\\{{\\{{{re.escape(var_name)}\\}}\\}}",
                # Padrão com espaços: {{ variavel }}
                f"\\{{\\{{\\s*{re.escape(var_name)}\\s*\\}}\\}}",
            ]
            
            substituicoes_feitas = 0
            for pattern in patterns:
                sql_antes = sql_processado
                sql_processado = re.sub(pattern, str(valor_formatado), sql_processado, flags=re.IGNORECASE)
                if sql_processado != sql_antes:
                    count = len(re.findall(pattern, sql_antes, flags=re.IGNORECASE))
                    substituicoes_feitas += count
                    logger.info(f"Substituída variável '{var_name}' por '{valor_formatado}' - {count} ocorrências")
            
            if substituicoes_feitas == 0:
                logger.warning(f"Variável '{var_name}' não foi encontrada no SQL para substituição")
        
        logger.info(f"SQL processado tem {len(sql_processado)} caracteres")
        
        # Verifica se ainda há variáveis não substituídas
        variaveis_restantes = re.findall(r'\{\{([^}]+)\}\}', sql_processado)
        if variaveis_restantes:
            logger.warning(f"Variáveis não substituídas encontradas: {variaveis_restantes}")
        
        # DEBUG: Prints diretos para mostrar resultado
        print(f"🔧 SQL processado (últimas 100 chars): ...{sql_processado[-100:]}")
        print(f"🔧 Variáveis não substituídas: {variaveis_restantes}")
        
        return sql_processado
    
    def _formatar_variavel(self, var_name, valor):
        """
        Formata automaticamente variáveis baseado no nome e valor
        Especialmente importante para variáveis de data
        """
        import re
        from datetime import datetime
        
        # Se valor é None ou vazio, retorna string vazia
        if valor is None or valor == '':
            return ''
        
        # Converter para string
        valor_str = str(valor).strip()
        
        # Se já está vazio após strip, retorna vazio
        if not valor_str:
            return ''
        
        # Detectar variáveis de data pelo nome
        nomes_data = [
            'data_vencimento', 'data_inicio', 'data_fim', 'data_pagamento',
            'data_cadastro', 'data_criacao', 'vencimento', 'inicio', 'fim'
        ]
        
        eh_variavel_data = any(nome in var_name.lower() for nome in nomes_data)
        
        if eh_variavel_data:
            print(f"📅 DETECTADA VARIÁVEL DE DATA: {var_name} = '{valor_str}'")
            return self._formatar_data_para_sql(valor_str)
        
        # Detectar variáveis numéricas que podem ser dias
        if var_name.lower() in ['dia1', 'dia2', 'dias'] and valor_str.isdigit():
            # Para variáveis de dia, manter como número
            return valor_str
        
        # Para outras variáveis, retornar como está
        return valor_str
    
    def _formatar_data_para_sql(self, valor_data):
        """
        Converte datas do formato brasileiro (DD/MM/AAAA) para formato SQL (YYYY-MM-DD)
        Também aceita outros formatos comuns
        """
        from datetime import datetime
        import re
        
        if not valor_data or valor_data.strip() == '':
            return 'CURRENT_DATE'  # Valor padrão para datas vazias
        
        valor_str = str(valor_data).strip()
        
        # Se é apenas um número (como "1"), tratar como erro e usar data atual
        if valor_str.isdigit() and len(valor_str) <= 2:
            print(f"⚠️  ERRO: Variável de data recebeu apenas número '{valor_str}' - usando data atual")
            return datetime.now().strftime('%Y-%m-%d')
        
        # Padrões de data para conversão
        padroes_data = [
            # Formato brasileiro: DD/MM/AAAA ou DD/MM/AA
            (r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', '%d/%m/%Y'),
            # Formato americano: YYYY-MM-DD (já no formato correto)
            (r'^(\d{4})-(\d{1,2})-(\d{1,2})$', '%Y-%m-%d'),
            # Formato ISO: YYYY/MM/DD
            (r'^(\d{4})/(\d{1,2})/(\d{1,2})$', '%Y/%m/%d'),
            # Formato brasileiro sem barras: DDMMAAAA
            (r'^(\d{2})(\d{2})(\d{4})$', '%d%m%Y'),
        ]
        
        for padrao, formato in padroes_data:
            if re.match(padrao, valor_str):
                try:
                    if formato == '%Y-%m-%d':
                        # Já está no formato correto
                        return valor_str
                    elif formato == '%d%m%Y':
                        # Formato DDMMAAAA -> DD/MM/AAAA primeiro
                        dia = valor_str[:2]
                        mes = valor_str[2:4]
                        ano = valor_str[4:]
                        data_obj = datetime.strptime(f"{dia}/{mes}/{ano}", '%d/%m/%Y')
                    else:
                        data_obj = datetime.strptime(valor_str, formato)
                    
                    # Converter para formato SQL
                    data_sql = data_obj.strftime('%Y-%m-%d')
                    print(f"✅ DATA CONVERTIDA: '{valor_str}' → '{data_sql}'")
                    return data_sql
                    
                except ValueError as e:
                    print(f"❌ ERRO ao converter data '{valor_str}': {e}")
                    continue
        
        # Se não conseguiu converter, verificar se é uma palavra-chave SQL
        palavras_sql = ['CURRENT_DATE', 'NOW()', 'TODAY']
        if valor_str.upper() in palavras_sql:
            return valor_str.upper()
        
        # Como último recurso, tentar interpretar como data atual se é um número pequeno
        if valor_str.isdigit() and int(valor_str) <= 31:
            print(f"⚠️  ASSUMINDO: '{valor_str}' é um dia do mês atual")
            hoje = datetime.now()
            try:
                data_assumida = hoje.replace(day=int(valor_str))
                return data_assumida.strftime('%Y-%m-%d')
            except ValueError:
                # Dia inválido para o mês atual
                pass
        
        # Se tudo falhar, usar data atual
        print(f"❌ NÃO FOI POSSÍVEL CONVERTER '{valor_str}' - usando data atual")
        return datetime.now().strftime('%Y-%m-%d')

class VariavelTemplate(models.Model):
    """
    Modelo para configurar variáveis individuais de um template SQL
    """
    TIPO_CHOICES = [
        ('text', 'Texto'),
        ('number', 'Número'),
        ('date', 'Data'),
        ('datetime', 'Data e Hora'),
        ('select', 'Lista de Opções'),
    ]
    
    template_sql = models.ForeignKey(
        'TemplateSQL',
        on_delete=models.CASCADE,
        related_name='variaveis',
        verbose_name="Template SQL"
    )
    
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome da Variável",
        help_text="Nome usado no SQL: {{nome_da_variavel}}"
    )
    
    label = models.CharField(
        max_length=200,
        verbose_name="Rótulo",
        help_text="Texto exibido no formulário para o usuário"
    )
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='text',
        verbose_name="Tipo do Campo"
    )
    
    obrigatorio = models.BooleanField(
        default=True,
        verbose_name="Obrigatório",
        help_text="Se o campo deve ser preenchido obrigatoriamente"
    )
    
    valor_padrao = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Valor Padrão",
        help_text="Valor pré-preenchido no formulário"
    )
    
    opcoes = models.TextField(
        blank=True,
        verbose_name="Opções",
        help_text="Para tipo 'Lista de Opções': uma opção por linha"
    )
    
    ordem = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Ordem de exibição no formulário"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    class Meta:
        verbose_name = "Variável do Template"
        verbose_name_plural = "Variáveis do Template"
        ordering = ['ordem', 'nome']
        unique_together = ['template_sql', 'nome']
    
    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"
    
    def get_opcoes_lista(self):
        """Retorna as opções como uma lista"""
        if self.opcoes:
            return [opcao.strip() for opcao in self.opcoes.split('\n') if opcao.strip()]
        return []
    
    def to_config_dict(self):
        """Converte para o formato usado no sistema existente"""
        return {
            'tipo': self.tipo,
            'label': self.label,
            'obrigatorio': self.obrigatorio,
            'valor_padrao': self.valor_padrao,
            'opcoes': self.get_opcoes_lista()
        }

class CredenciaisBancoDados(models.Model):
    TIPO_BANCO_CHOICES = [
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
        ('sqlserver', 'SQL Server'),
        ('oracle', 'Oracle'),
        ('clickhouse', 'ClickHouse'),
    ]

    titulo = models.CharField(max_length=100, verbose_name="Título")
    tipo_banco = models.CharField(max_length=20, choices=TIPO_BANCO_CHOICES, verbose_name="Tipo de Banco")
    host = models.CharField(max_length=255, verbose_name="Host")
    porta = models.IntegerField(verbose_name="Porta")
    banco = models.CharField(max_length=100, verbose_name="Nome do Banco")
    usuario = models.CharField(max_length=100, verbose_name="Usuário")
    senha = models.CharField(max_length=100, verbose_name="Senha")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")

    class Meta:
        verbose_name = "Credencial de Banco de Dados"
        verbose_name_plural = "Credenciais de Banco de Dados"

    def __str__(self):
        return f"{self.titulo} - {self.tipo_banco} ({self.host})"

    def get_connection_string(self):
        if self.tipo_banco == 'mysql':
            return f"mysql://{self.usuario}:{self.senha}@{self.host}:{self.porta}/{self.banco}"
        elif self.tipo_banco == 'postgresql':
            return f"postgresql://{self.usuario}:{self.senha}@{self.host}:{self.porta}/{self.banco}"
        elif self.tipo_banco == 'sqlserver':
            return f"mssql://{self.usuario}:{self.senha}@{self.host}:{self.porta}/{self.banco}"
        elif self.tipo_banco == 'oracle':
            return f"oracle://{self.usuario}:{self.senha}@{self.host}:{self.porta}/{self.banco}"
        elif self.tipo_banco == 'clickhouse':
            return f"clickhouse://{self.usuario}:{self.senha}@{self.host}:{self.porta}/{self.banco}"
        return None

class CredenciaisHubsoft(models.Model):
    titulo = models.CharField(max_length=100, verbose_name="Título")
    client_id = models.CharField(max_length=100, verbose_name="Client ID")
    client_secret = models.CharField(max_length=100, verbose_name="Client Secret")
    username = models.EmailField(verbose_name="Username")
    password = models.CharField(max_length=100, verbose_name="Password")
    url_base = models.URLField(verbose_name="URL Base")
    url_token = models.URLField(verbose_name="URL Token")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")

    class Meta:
        verbose_name = "Credencial Hubsoft"
        verbose_name_plural = "Credenciais Hubsoft"

    def __str__(self):
        return f"{self.titulo} - {self.username}"

class ClienteConsultado(models.Model):
    codigo_cliente = models.CharField(max_length=50, verbose_name="Código do Cliente")
    nome_razaosocial = models.CharField(max_length=255, verbose_name="Nome/Razão Social")
    telefone_corrigido = models.CharField(max_length=20, verbose_name="Telefone Corrigido", blank=True, null=True)
    id_fatura = models.CharField(max_length=50, verbose_name="ID da Fatura", null=True, blank=True)
    vencimento_fatura = models.DateField(verbose_name="Vencimento da Fatura", null=True, blank=True)
    valor_fatura = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor da Fatura", null=True, blank=True)
    pix = models.CharField(max_length=255, verbose_name="Código PIX", null=True, blank=True)
    codigo_barras = models.CharField(max_length=255, verbose_name="Código de Barras", null=True, blank=True)
    link_boleto = models.URLField(verbose_name="Link do Boleto", null=True, blank=True)
    
    # NOVO: Campo para dados dinâmicos adicionais
    dados_dinamicos = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name="Dados Dinâmicos",
        help_text="Dados adicionais do cliente que podem ser usados em HSM e Flow"
    )
    
    # Relacionamento para identificar a origem dos dados (empresa/base)
    credencial_banco = models.ForeignKey(
        CredenciaisBancoDados,
        on_delete=models.CASCADE,
        verbose_name="Credencial de Banco",
        help_text="Identifica de qual base/empresa este cliente foi consultado",
        null=True,
        blank=True
    )
    
    data_criacao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(null=True, blank=True, verbose_name="Data de Atualização")

    class Meta:
        verbose_name = "Cliente Consultado"
        verbose_name_plural = "Clientes Consultados"
        # Unicidade baseada em código_cliente + credencial_banco (empresa)
        unique_together = ['codigo_cliente', 'credencial_banco']

    def __str__(self):
        empresa_info = f" - {self.credencial_banco.titulo}" if self.credencial_banco else ""
        return f"{self.codigo_cliente}{empresa_info} - {self.nome_razaosocial}"
    
    def get_dado_dinamico(self, chave, valor_padrao=None):
        """
        Obtém um valor dos dados dinâmicos
        Exemplo: cliente.get_dado_dinamico('endereco', 'Não informado')
        """
        if not self.dados_dinamicos:
            return valor_padrao
        return self.dados_dinamicos.get(chave, valor_padrao)
    
    def set_dado_dinamico(self, chave, valor):
        """
        Define um valor nos dados dinâmicos
        Exemplo: cliente.set_dado_dinamico('endereco', 'Rua ABC, 123')
        """
        if not self.dados_dinamicos:
            self.dados_dinamicos = {}
        self.dados_dinamicos[chave] = valor
        self.save(update_fields=['dados_dinamicos', 'data_atualizacao'])
    
    def get_todos_dados_dinamicos(self):
        """
        Retorna todos os dados dinâmicos como dicionário
        """
        return self.dados_dinamicos or {}
    
    def limpar_dados_dinamicos(self):
        """
        Remove todos os dados dinâmicos
        """
        self.dados_dinamicos = {}
        self.save(update_fields=['dados_dinamicos', 'data_atualizacao'])
    
    def get_dados_completos(self):
        """
        Retorna todos os dados do cliente (fixos + dinâmicos) como dicionário
        Útil para HSM e Flow
        """
        dados = {
            'codigo_cliente': self.codigo_cliente,
            'nome_razaosocial': self.nome_razaosocial,
            'telefone_corrigido': self.telefone_corrigido,
            'id_fatura': self.id_fatura,
            'vencimento_fatura': self.vencimento_fatura,
            'valor_fatura': self.valor_fatura,
            'pix': self.pix,
            'codigo_barras': self.codigo_barras,
            'link_boleto': self.link_boleto,
            'empresa': self.credencial_banco.titulo if self.credencial_banco else None,
            'data_criacao': self.data_criacao,
            'data_atualizacao': self.data_atualizacao,
        }
        
        # Adiciona dados dinâmicos
        if self.dados_dinamicos:
            dados.update(self.dados_dinamicos)
        
        return dados

class ConsultaExecucao(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('executando', 'Executando'),
        ('concluida', 'Concluída'),
        ('cancelada', 'Cancelada'),
        ('erro', 'Erro'),
    ]
    
    titulo = models.CharField(max_length=255, verbose_name="Título da Execução")
    template_sql = models.ForeignKey(TemplateSQL, on_delete=models.CASCADE, verbose_name="Template SQL")
    credencial_hubsoft = models.ForeignKey(
        CredenciaisHubsoft, 
        on_delete=models.CASCADE, 
        verbose_name="Credencial Hubsoft",
        null=True,
        blank=True,
        help_text="Obrigatório apenas se 'Pular Consulta na API' estiver desmarcado"
    )
    credencial_banco = models.ForeignKey(CredenciaisBancoDados, on_delete=models.CASCADE, verbose_name="Credencial Banco de Dados")
    valores_variaveis = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name="Valores das Variáveis",
        help_text="Valores fornecidos pelo usuário para as variáveis do template"
    )
    # NOVO: Campo para pular consulta da API
    pular_consulta_api = models.BooleanField(
        default=False,
        verbose_name="Pular Consulta na API",
        help_text="Se marcado, não consultará dados financeiros na API. Útil para campanhas que usam apenas dados do SQL."
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status")
    total_registros_sql = models.IntegerField(default=0, verbose_name="Total de Registros SQL")
    total_consultados_api = models.IntegerField(default=0, verbose_name="Total Consultados API")
    total_erros = models.IntegerField(default=0, verbose_name="Total de Erros")
    log_execucao = models.TextField(blank=True, null=True, verbose_name="Log de Execução")
    data_inicio = models.DateTimeField(auto_now_add=True, verbose_name="Data de Início")
    data_fim = models.DateTimeField(null=True, blank=True, verbose_name="Data de Fim")

    class Meta:
        verbose_name = "Execução de Consulta"
        verbose_name_plural = "Execuções de Consultas"
        ordering = ['-data_inicio']

    def clean(self):
        """Validação personalizada do modelo"""
        from django.core.exceptions import ValidationError
        
        # Se não pular API, credencial Hubsoft é obrigatória
        if not self.pular_consulta_api and not self.credencial_hubsoft:
            raise ValidationError({
                'credencial_hubsoft': 'Credencial Hubsoft é obrigatória quando a consulta da API está habilitada.'
            })
        
        # Se pular API, credencial Hubsoft não é necessária
        if self.pular_consulta_api and self.credencial_hubsoft:
            # Apenas aviso - não é erro, pode manter a credencial
            pass

    def __str__(self):
        return f"{self.titulo} - {self.status} ({self.data_inicio.strftime('%d/%m/%Y %H:%M')})"

    def atualizar_status(self, status, log=None):
        self.status = status
        if log:
            self.log_execucao = log
        if status in ['concluida', 'erro']:
            self.data_fim = timezone.now()
        self.save()
    
    @property
    def clientes_processados(self):
        """Retorna o total de clientes processados nesta execução"""
        return ConsultaCliente.objects.filter(execucao=self).count()
    
    @property
    def clientes_com_sucesso(self):
        """Retorna o total de clientes processados com sucesso"""
        return ConsultaCliente.objects.filter(execucao=self, sucesso_api=True).count()
    
    @property
    def clientes_com_erro(self):
        """Retorna o total de clientes processados com erro"""
        return ConsultaCliente.objects.filter(execucao=self, sucesso_api=False).count()

class ConsultaCliente(models.Model):
    execucao = models.ForeignKey(ConsultaExecucao, on_delete=models.CASCADE, verbose_name="Execução", null=True, blank=True)
    cliente = models.ForeignKey(ClienteConsultado, on_delete=models.CASCADE, verbose_name="Cliente")
    dados_originais_sql = models.JSONField(null=True, blank=True, verbose_name="Dados Originais SQL", help_text="Dados retornados da consulta SQL")
    dados_api_response = models.JSONField(null=True, blank=True, verbose_name="Resposta da API", help_text="Dados retornados da API")
    sucesso_api = models.BooleanField(default=False, verbose_name="Sucesso na API")
    erro_api = models.TextField(blank=True, null=True, verbose_name="Erro da API")
    data_consulta = models.DateTimeField(auto_now_add=True, verbose_name="Data da Consulta")

    class Meta:
        verbose_name = "Consulta de Cliente"
        verbose_name_plural = "Consultas de Clientes"
        ordering = ['-data_consulta']
        unique_together = ['execucao', 'cliente']

    def __str__(self):
        return f"{self.cliente.nome_razaosocial} - {self.execucao.titulo if self.execucao else 'Sem execução'} ({self.data_consulta.strftime('%d/%m/%Y %H:%M')})"

class MatrixAPIConfig(models.Model):
    
    """
    Configurações da API Matrix para envio de HSM
    
    Armazena as configurações de conexão com a API Matrix,
    incluindo URL base e chave de autenticação.
    """
    
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome da Configuração",
        help_text="Nome para identificar esta configuração"
    )
    
    base_url = models.URLField(
        verbose_name="URL Base da API",
        help_text="URL base da API Matrix (ex: https://megalink.matrixdobrasil.ai)"
    )
    
    api_key = models.CharField(
        max_length=255,
        verbose_name="Chave da API",
        help_text="Chave de autenticação da API Matrix"
    )
    
    cod_conta = models.IntegerField(
        verbose_name="Código da Conta",
        help_text="Código da conta na Matrix"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se esta configuração está ativa"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    class Meta:
        verbose_name = "Configuração da API Matrix"
        verbose_name_plural = "Configurações da API Matrix"
        ordering = ['-ativo', 'nome']
    
    def __str__(self):
        return f"{self.nome} - {self.base_url}"
    
    def get_config_dict(self):
        """Retorna configuração como dicionário"""
        return {
            'base_url': self.base_url,
            'api_key': self.api_key,
            'cod_conta': self.cod_conta
        }
    
class HSMTemplate(models.Model):
    """
    Templates de HSM para envio
    
    Armazena os templates de mensagens HSM com suas configurações
    e variáveis necessárias.
    """
    
    TIPO_ENVIO_CHOICES = [
        (1, 'Atendimento Automático'),
        (2, 'Notificação'),
        (3, 'Fila de Atendimento'),
    ]
    
    TIPO_TEMPLATE_CHOICES = [
        ('padrao', 'Padrão'),
        ('pagamento', 'Pagamento'),
    ]
    
    nome = models.CharField(
        max_length=200,
        verbose_name="Nome do Template",
        help_text="Nome descritivo do template HSM"
    )
    
    hsm_id = models.IntegerField(
        verbose_name="ID do HSM",
        help_text="ID do template HSM na Matrix"
    )
    
    cod_flow = models.IntegerField(
        verbose_name="Código do Flow",
        help_text="Código do flow de atendimento",
        null=True,
        blank=True
    )
    
    tipo_envio = models.IntegerField(
        choices=TIPO_ENVIO_CHOICES,
        default=1,
        verbose_name="Tipo de Envio",
        help_text="Tipo de envio do HSM"
    )
    
    tipo_template = models.CharField(
        max_length=20,
        choices=TIPO_TEMPLATE_CHOICES,
        default='padrao',
        verbose_name="Tipo de Template",
        help_text="Define se é um template padrão ou de pagamento"
    )
    
    descricao = models.TextField(
        verbose_name="Descrição",
        help_text="Descrição detalhada do template",
        blank=True
    )
    
    variaveis_descricao = models.JSONField(
        verbose_name="Descrição das Variáveis",
        help_text="Descrição das variáveis do HSM (ex: {'1': 'Nome do Cliente', '2': 'Valor'})",
        default=dict,
        blank=True
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se este template está ativo"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    class Meta:
        verbose_name = "Template HSM"
        verbose_name_plural = "Templates HSM"
        ordering = ['nome']
    
    def __str__(self):
        return f"{self.nome} (ID: {self.hsm_id})"
    
    def get_variaveis_descricao(self):
        """Retorna descrição das variáveis formatada"""
        if isinstance(self.variaveis_descricao, str):
            return json.loads(self.variaveis_descricao)
        return self.variaveis_descricao

class EnvioHSMMatrix(models.Model):
    """
    Modelo para controle de envios de HSM via API Matrix
    
    Permite configurar e executar envios de HSM baseados em templates,
    usando configurações específicas da API Matrix e dados de consultas.
    """
    
    STATUS_ENVIO_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviando', 'Enviando'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
        ('erro', 'Erro'),
        ('pausado', 'Pausado'),
    ]
    
    titulo = models.CharField(
        max_length=255,
        verbose_name="Título do Envio",
        help_text="Título descritivo para identificar este envio"
    )
    
    hsm_template = models.ForeignKey(
        HSMTemplate,
        on_delete=models.CASCADE,
        verbose_name="Template HSM Principal",
        help_text="Template HSM principal que será enviado quando todas as variáveis estiverem preenchidas"
    )
    
    hsm_template_contingencia = models.ForeignKey(
        HSMTemplate,
        on_delete=models.CASCADE,
        verbose_name="Template HSM de Contingência",
        help_text="Template HSM alternativo usado quando alguma variável do template principal estiver vazia",
        null=True,
        blank=True,
        related_name='envios_contingencia'
    )
    
    configuracao_variaveis_contingencia = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuração das Variáveis - Contingência",
        help_text="Mapeamento das variáveis do HSM de contingência com campos dos dados"
    )
    
    # Campos para o segundo HSM (envio duplo)
    habilitar_segundo_hsm = models.BooleanField(
        default=False,
        verbose_name="Habilitar Segundo HSM",
        help_text="Ativa o envio de um segundo HSM após o primeiro"
    )
    
    hsm_template_segundo = models.ForeignKey(
        HSMTemplate,
        on_delete=models.CASCADE,
        verbose_name="Template HSM Segundo",
        help_text="Template HSM que será enviado como segundo HSM",
        null=True,
        blank=True,
        related_name='envios_segundo'
    )
    
    configuracao_variaveis_segundo = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuração das Variáveis - Segundo HSM",
        help_text="Mapeamento das variáveis do segundo HSM com campos dos dados"
    )
    
    intervalo_segundo_hsm = models.PositiveIntegerField(
        default=3,
        verbose_name="Intervalo para Segundo HSM (segundos)",
        help_text="Tempo em segundos para aguardar antes de enviar o segundo HSM"
    )
    
    # Campos específicos para o segundo HSM de pagamento
    razao_social_empresa_segundo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Razão Social da Empresa - Segundo HSM",
        help_text="Razão social para PIX do segundo HSM (caso seja pagamento)"
    )
    
    cnpj_empresa_segundo = models.CharField(
        max_length=18,
        blank=True,
        verbose_name="CNPJ da Empresa - Segundo HSM",
        help_text="CNPJ da empresa para PIX do segundo HSM (caso seja pagamento)"
    )
    
    nome_produto_padrao_segundo = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nome do Produto Padrão - Segundo HSM",
        help_text="Nome padrão do produto para o segundo HSM"
    )
    
    configuracao_pagamento_segundo = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuração de Pagamento - Segundo HSM",
        help_text="Configurações específicas para envio de HSM de pagamento (segundo HSM)"
    )
    
    matrix_api_config = models.ForeignKey(
        MatrixAPIConfig,
        on_delete=models.CASCADE,
        verbose_name="Configuração da API Matrix",
        help_text="Configuração da API Matrix para envio"
    )
    
    consulta_execucao = models.ForeignKey(
        ConsultaExecucao,
        on_delete=models.CASCADE,
        verbose_name="Execução da Consulta",
        help_text="Execução da consulta que fornecerá os dados para envio",
        null=True,
        blank=True
    )
    
    status_envio = models.CharField(
        max_length=20,
        choices=STATUS_ENVIO_CHOICES,
        default='pendente',
        verbose_name="Status do Envio"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    data_inicio_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Início do Envio"
    )
    
    data_fim_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Fim do Envio"
    )
    
    total_clientes = models.IntegerField(
        default=0,
        verbose_name="Total de Clientes"
    )
    
    total_enviados = models.IntegerField(
        default=0,
        verbose_name="Total Enviados"
    )
    
    total_erros = models.IntegerField(
        default=0,
        verbose_name="Total de Erros"
    )
    
    total_pendentes = models.IntegerField(
        default=0,
        verbose_name="Total Pendentes"
    )
    
    log_execucao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Log de Execução",
        help_text="Log detalhado da execução do envio"
    )
    
    configuracao_variaveis = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuração das Variáveis",
        help_text="Mapeamento das variáveis do HSM com campos dos dados"
    )
    
    # Campos específicos para HSM de pagamento
    configuracao_pagamento_hsm = models.ForeignKey(
        'ConfiguracaoPagamentoHSM',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Configuração de Pagamento",
        help_text="Configuração reutilizável para dados de pagamento"
    )
    
    configuracao_pagamento = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuração de Pagamento Manual",
        help_text="Configurações específicas para envio de HSM com pagamento (usado quando não há configuração selecionada)"
    )
    
    razao_social_empresa = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Razão Social da Empresa",
        help_text="Razão social para PIX (pix.nom_empresa)"
    )
    
    cnpj_empresa = models.CharField(
        max_length=18,
        blank=True,
        verbose_name="CNPJ da Empresa",
        help_text="CNPJ da empresa sem formatação para PIX (pix.chave)"
    )
    
    nome_produto_padrao = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Nome do Produto Padrão",
        help_text="Nome padrão do produto (ex: 'Fatura NomeDaEmpresa')"
    )
    
    filtros_adicionais = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Filtros Adicionais",
        help_text="Filtros adicionais para seleção de clientes"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    # Campos para envio de HSM com mídia
    enviar_com_midia = models.BooleanField(
        default=False,
        verbose_name="Enviar com Mídia",
        help_text="Marque para enviar HSM com imagem ou arquivo anexado"
    )
    
    arquivo_midia = models.FileField(
        upload_to='hsm_midias/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name="Arquivo de Mídia",
        help_text="Upload de imagem ou arquivo para envio com HSM (será acessível via URL)"
    )
    
    url_midia = models.URLField(
        blank=True,
        verbose_name="URL da Mídia",
        help_text="URL externa da mídia (alternativa ao upload de arquivo). Usada quando 'Enviar com Mídia' está marcado."
    )
    
    class Meta:
        verbose_name = "Envio HSM Matrix"
        verbose_name_plural = "Envios HSM Matrix"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"{self.titulo} - {self.get_status_envio_display()} ({self.data_criacao.strftime('%d/%m/%Y %H:%M')})"
    
    def atualizar_status(self, status, log=None):
        """Atualiza o status do envio e registra log"""
        self.status_envio = status
        
        if log:
            if self.log_execucao:
                self.log_execucao += f"\n{timezone.now().strftime('%d/%m/%Y %H:%M:%S')} - {log}"
            else:
                self.log_execucao = f"{timezone.now().strftime('%d/%m/%Y %H:%M:%S')} - {log}"
        
        # Atualiza datas baseado no status
        if status == 'enviando' and not self.data_inicio_envio:
            self.data_inicio_envio = timezone.now()
        elif status in ['concluido', 'erro', 'cancelado']:
            self.data_fim_envio = timezone.now()
        
        self.save()
    
    def calcular_totais(self):
        """Calcula os totais baseado nos envios individuais"""
        from .models import EnvioHSMIndividual
        
        envios = EnvioHSMIndividual.objects.filter(envio_matrix=self)
        
        self.total_clientes = envios.count()
        self.total_enviados = envios.filter(status='enviado').count()
        self.total_erros = envios.filter(status='erro').count()
        self.total_pendentes = envios.filter(status='pendente').count()
        
        self.save()
    
    def get_progresso_percentual(self):
        """Retorna o percentual de progresso do envio"""
        if self.total_clientes == 0:
            return 0
        
        return round((self.total_enviados + self.total_erros) / self.total_clientes * 100, 2)
    
    def get_url_midia(self):
        """
        Retorna a URL da mídia para uso no envio
        Prioriza arquivo_midia (se houver) sobre url_midia
        """
        if self.enviar_com_midia:
            if self.arquivo_midia:
                # Retorna a URL completa do arquivo
                from django.conf import settings
                if hasattr(self.arquivo_midia, 'url'):
                    # Se MEDIA_URL é relativa, precisamos adicionar o domínio
                    media_url = self.arquivo_midia.url
                    if media_url.startswith('/'):
                        # Tenta pegar o domínio do request ou das settings
                        # Por enquanto retorna apenas a URL relativa
                        return media_url
                    return media_url
            elif self.url_midia:
                return self.url_midia
        return None
    
    def pode_iniciar(self):
        """Verifica se o envio pode ser iniciado"""
        return (
            self.status_envio in ['pendente', 'pausado'] and
            self.ativo and
            self.hsm_template.ativo and
            self.matrix_api_config.ativo and
            self.consulta_execucao and
            self.consulta_execucao.status == 'concluida'
        )

class ConfiguracaoPagamentoHSM(models.Model):
    """
    Modelo para armazenar configurações de pagamento reutilizáveis
    para templates HSM de pagamento
    """
    
    nome = models.CharField(
        max_length=200,
        verbose_name="Nome da Configuração",
        help_text="Nome descritivo para identificar esta configuração"
    )
    
    descricao = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada da configuração"
    )
    
    # Dados da empresa
    razao_social_empresa = models.CharField(
        max_length=255,
        verbose_name="Razão Social da Empresa",
        help_text="Razão social para PIX (pix.nom_empresa)"
    )
    
    cnpj_empresa = models.CharField(
        max_length=18,
        verbose_name="CNPJ da Empresa",
        help_text="CNPJ da empresa sem formatação para PIX (pix.chave)"
    )
    
    # Dados do produto
    nome_produto_padrao = models.CharField(
        max_length=255,
        verbose_name="Nome do Produto Padrão",
        help_text="Nome padrão do produto (ex: 'Fatura Mensal')"
    )
    
    tipo_produto = models.CharField(
        max_length=50,
        choices=[
            ('digital-goods', 'Bens Digitais'),
            ('physical-goods', 'Bens Físicos'),
            ('services', 'Serviços'),
        ],
        default='digital-goods',
        verbose_name="Tipo de Produto"
    )
    
    # Valores padrão
    val_imposto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Valor do Imposto",
        help_text="Valor padrão do imposto"
    )
    
    val_desconto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Valor do Desconto",
        help_text="Valor padrão do desconto"
    )
    
    # Variáveis adicionais do flow
    variaveis_flow_padrao = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Variáveis Padrão do Flow",
        help_text="Variáveis adicionais que serão enviadas para o flow"
    )
    
    # Configurações extras
    configuracao_extra = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configurações Extras",
        help_text="Configurações adicionais em formato JSON"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    class Meta:
        verbose_name = "Configuração de Pagamento HSM"
        verbose_name_plural = "Configurações de Pagamento HSM"
        ordering = ['-ativo', 'nome']
    
    def __str__(self):
        return f"{self.nome} - {self.razao_social_empresa}"
    
    def get_dados_pagamento(self, cliente=None):
        """
        Retorna os dados de pagamento formatados para uso no HSM
        
        Args:
            cliente: Objeto cliente opcional para personalização
        
        Returns:
            dict: Dados formatados para hsm_parametros
        """
        # Prepara dados básicos
        dados = {
            "pedido_info": {
                "tipo": self.tipo_produto,
                "val_imposto": float(self.val_imposto),
                "val_desconto": float(self.val_desconto),
                "pix": {
                    "nom_empresa": self.razao_social_empresa,
                    "chave": self.cnpj_empresa,
                    "chave_tipo": "CNPJ"
                }
            }
        }
        
        # Adiciona configurações extras se existirem
        if self.configuracao_extra:
            dados.update(self.configuracao_extra)
        
        return dados

class EnvioHSMIndividual(models.Model):
    """
    Modelo para controle individual de cada HSM enviado
    
    Registra o status e resultado de cada envio individual de HSM
    """
    
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviando', 'Enviando'),
        ('enviado', 'Enviado'),
        ('erro', 'Erro'),
        ('cancelado', 'Cancelado'),
    ]
    
    envio_matrix = models.ForeignKey(
        EnvioHSMMatrix,
        on_delete=models.CASCADE,
        related_name='envios_individuais',
        verbose_name="Envio Matrix"
    )
    
    cliente = models.ForeignKey(
        ClienteConsultado,
        on_delete=models.CASCADE,
        verbose_name="Cliente"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        verbose_name="Status"
    )
    
    data_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data do Envio"
    )
    
    resposta_api = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Resposta da API",
        help_text="Resposta completa da API Matrix"
    )
    
    erro_detalhado = models.TextField(
        blank=True,
        null=True,
        verbose_name="Erro Detalhado",
        help_text="Detalhes do erro caso ocorra"
    )
    
    template_usado = models.CharField(
        max_length=20,
        choices=[
            ('principal', 'Principal'),
            ('contingencia', 'Contingência'),
        ],
        default='principal',
        verbose_name="Template Usado",
        help_text="Indica se foi usado o template principal ou de contingência"
    )
    
    # Campos para controle de envio duplo
    hsm_enviado = models.CharField(
        max_length=20,
        choices=[
            ('primeiro', 'Primeiro HSM'),
            ('segundo', 'Segundo HSM'),
        ],
        default='primeiro',
        verbose_name="HSM Enviado",
        help_text="Indica se este envio é do primeiro ou segundo HSM"
    )
    
    envio_relacionado = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Envio Relacionado",
        help_text="Vincula os dois envios do mesmo cliente (primeiro e segundo HSM)"
    )
    
    tentativas = models.PositiveIntegerField(
        default=0,
        verbose_name="Tentativas de Envio"
    )
    
    variaveis_utilizadas = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Variáveis Utilizadas",
        help_text="Variáveis que foram utilizadas no envio"
    )
    
    # Campos específicos para HSM de pagamento
    dados_pagamento = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Dados de Pagamento",
        help_text="Dados específicos do pagamento (hsm_parametros)"
    )
    
    url_file = models.URLField(
        blank=True,
        verbose_name="URL do Arquivo",
        help_text="Link do arquivo/mídia (boleto PDF, imagem, etc.) enviado com o HSM"
    )
    
    # Campo para controle de ativação
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se este envio individual está ativo"
    )
    
    # Campo para armazenar as variáveis do flow que foram enviadas
    flow_variaveis_enviadas = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Variáveis do Flow Enviadas",
        help_text="Variáveis que foram enviadas para o flow no momento do envio"
    )
    
    class Meta:
        verbose_name = "Envio HSM Individual"
        verbose_name_plural = "Envios HSM Individuais"
        ordering = ['-data_envio']
        unique_together = ['envio_matrix', 'cliente', 'hsm_enviado']
    
    def __str__(self):
        return f"{self.cliente.nome_razaosocial} - {self.get_status_display()}"
    
    def marcar_enviado(self, resposta_api=None):
        """Marca o HSM como enviado com sucesso"""
        self.status = 'enviado'
        self.data_envio = timezone.now()
        if resposta_api:
            self.resposta_api = resposta_api
        self.save()
    
    def marcar_erro(self, erro, resposta_api=None):
        """Marca o HSM como erro"""
        self.status = 'erro'
        self.data_envio = timezone.now()
        self.erro_detalhado = erro
        self.tentativas += 1
        if resposta_api:
            self.resposta_api = resposta_api
        self.save()
# Importar modelos de log
from .models_log import APILog, APILogEstatistica

