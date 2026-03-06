from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, CheckConstraint
from campanhas.models import TemplateSQL, ConsultaExecucao, ClienteConsultado
import re
import json
from datetime import datetime, timedelta


class BaseLeads(models.Model):
    """
    Base de leads importada via CSV
    Armazena metadados da importação e configuração das colunas
    """
    
    nome = models.CharField(
        max_length=255,
        verbose_name="Nome da Base",
        help_text="Nome descritivo para identificar esta base de leads"
    )
    
    descricao = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada sobre esta base de leads"
    )
    
    arquivo_original_nome = models.CharField(
        max_length=255,
        verbose_name="Nome do Arquivo Original",
        help_text="Nome do arquivo CSV que foi importado"
    )
    
    # Totais
    total_leads = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Leads",
        help_text="Total de linhas processadas do CSV"
    )
    
    total_validos = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Válidos",
        help_text="Leads com email válido"
    )
    
    total_invalidos = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Inválidos",
        help_text="Leads com email inválido ou dados faltando"
    )
    
    # Metadados das colunas do CSV
    colunas_disponiveis = models.JSONField(
        default=list,
        verbose_name="Colunas Disponíveis",
        help_text="Lista de todas as colunas encontradas no CSV"
    )
    
    coluna_email = models.CharField(
        max_length=100,
        verbose_name="Coluna de Email",
        help_text="Nome da coluna que contém o email"
    )
    
    coluna_nome = models.CharField(
        max_length=100,
        verbose_name="Coluna de Nome",
        help_text="Nome da coluna que contém o nome do lead"
    )
    
    # Configurações de importação
    delimitador_usado = models.CharField(
        max_length=5,
        default=';',
        verbose_name="Delimitador",
        help_text="Delimitador usado no CSV (;, ,, tab)"
    )
    
    encoding_usado = models.CharField(
        max_length=20,
        default='utf-8',
        verbose_name="Encoding",
        help_text="Encoding do arquivo CSV"
    )
    
    # Controle
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se esta base está ativa para uso"
    )
    
    data_importacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Importação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    class Meta:
        verbose_name = "Base de Leads"
        verbose_name_plural = "Bases de Leads"
        ordering = ['-data_importacao']
    
    def __str__(self):
        return f"{self.nome} ({self.total_validos} leads válidos)"
    
    def get_taxa_validos(self):
        """Retorna percentual de leads válidos"""
        if self.total_leads == 0:
            return 0
        return round((self.total_validos / self.total_leads) * 100, 2)


class Lead(models.Model):
    """
    Lead individual importado do CSV
    """
    
    base_leads = models.ForeignKey(
        BaseLeads,
        on_delete=models.CASCADE,
        related_name='leads',
        verbose_name="Base de Leads"
    )
    
    email = models.EmailField(
        verbose_name="Email",
        help_text="Email do lead"
    )
    
    nome = models.CharField(
        max_length=255,
        verbose_name="Nome",
        help_text="Nome do lead"
    )
    
    # Dados adicionais dinâmicos do CSV
    dados_adicionais = models.JSONField(
        default=dict,
        verbose_name="Dados Adicionais",
        help_text="Todas as outras colunas do CSV (Telefone, Local, etc.)"
    )
    
    # Controle
    linha_original = models.PositiveIntegerField(
        verbose_name="Linha Original",
        help_text="Número da linha no CSV original"
    )
    
    valido = models.BooleanField(
        default=True,
        verbose_name="Válido",
        help_text="Se o lead tem dados válidos (email principalmente)"
    )
    
    motivo_invalido = models.TextField(
        blank=True,
        verbose_name="Motivo Inválido",
        help_text="Razão pela qual o lead foi marcado como inválido"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ['linha_original']
        unique_together = ['base_leads', 'email']  # Email único dentro de cada base
    
    def __str__(self):
        return f"{self.nome} ({self.email})"
    
    def get_dados_completos(self):
        """
        Retorna todos os dados do lead em formato compatível com templates
        Similar ao método get_dados_completos() de ClienteConsultado
        """
        dados = {
            'email': self.email,
            'nome': self.nome,
            'nome_destinatario': self.nome,
            'email_destinatario': self.email,
        }
        
        # Adicionar dados adicionais
        if self.dados_adicionais:
            dados.update(self.dados_adicionais)
        
        return dados


class ConfiguracaoServidorEmail(models.Model):
    """
    Configurações do servidor SMTP para envio de emails
    """
    
    nome = models.CharField(
        max_length=200,
        verbose_name="Nome da Configuração",
        help_text="Nome para identificar esta configuração SMTP"
    )
    
    servidor_smtp = models.CharField(
        max_length=255,
        verbose_name="Servidor SMTP",
        help_text="Endereço do servidor SMTP (ex: smtp.gmail.com)"
    )
    
    porta = models.IntegerField(
        verbose_name="Porta SMTP",
        default=587,
        help_text="Porta do servidor SMTP (587 para TLS, 465 para SSL, 25 para sem criptografia)"
    )
    
    usuario = models.CharField(
        max_length=255,
        verbose_name="Usuário",
        help_text="Usuário para autenticação no servidor SMTP"
    )
    
    senha = models.CharField(
        max_length=255,
        verbose_name="Senha",
        help_text="Senha para autenticação no servidor SMTP"
    )
    
    usar_tls = models.BooleanField(
        default=True,
        verbose_name="Usar TLS",
        help_text="Habilita criptografia TLS"
    )
    
    usar_ssl = models.BooleanField(
        default=False,
        verbose_name="Usar SSL",
        help_text="Habilita criptografia SSL"
    )
    
    email_remetente = models.EmailField(
        verbose_name="Email do Remetente",
        help_text="Email que aparecerá como remetente"
    )
    
    nome_remetente = models.CharField(
        max_length=255,
        verbose_name="Nome do Remetente",
        help_text="Nome que aparecerá como remetente",
        blank=True
    )
    
    timeout = models.PositiveIntegerField(
        default=30,
        verbose_name="Timeout (segundos)",
        help_text="Tempo limite para conexão SMTP"
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
    
    data_ultimo_teste = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data do Último Teste",
        help_text="Data do último teste de conexão bem-sucedido"
    )
    
    resultado_ultimo_teste = models.TextField(
        blank=True,
        verbose_name="Resultado do Último Teste",
        help_text="Resultado detalhado do último teste de conexão"
    )
    
    class Meta:
        verbose_name = "Configuração do Servidor de Email"
        verbose_name_plural = "Configurações dos Servidores de Email"
        ordering = ['-ativo', 'nome']
    
    def __str__(self):
        return "{} ({}:{})".format(self.nome, self.servidor_smtp, self.porta)
    
    def clean(self):
        """Validação personalizada do modelo"""
        if self.usar_tls and self.usar_ssl:
            raise ValidationError("Não é possível usar TLS e SSL simultaneamente")
    
    def testar_conexao(self):
        """
        Testa a conexão SMTP
        Retorna: (sucesso: bool, mensagem: str)
        """
        import smtplib
        
        try:
            # Criar conexão
            if self.usar_ssl:
                servidor = smtplib.SMTP_SSL(self.servidor_smtp, self.porta, timeout=self.timeout)
            else:
                servidor = smtplib.SMTP(self.servidor_smtp, self.porta, timeout=self.timeout)
                if self.usar_tls:
                    servidor.starttls()
            
            # Autenticar
            servidor.login(self.usuario, self.senha)
            
            # Fechar conexão
            servidor.quit()
            
            # Registrar teste bem-sucedido
            self.data_ultimo_teste = timezone.now()
            self.resultado_ultimo_teste = "Conexão testada com sucesso"
            self.save(update_fields=['data_ultimo_teste', 'resultado_ultimo_teste'])
            
            return True, "Conexão SMTP testada com sucesso"
            
        except Exception as e:
            erro = f"Erro na conexão SMTP: {str(e)}"
            self.resultado_ultimo_teste = erro
            self.save(update_fields=['resultado_ultimo_teste'])
            return False, erro
    
    def get_config_dict(self):
        """Retorna configuração como dicionário para uso em serviços"""
        return {
            'servidor_smtp': self.servidor_smtp,
            'porta': self.porta,
            'usuario': self.usuario,
            'senha': self.senha,
            'usar_tls': self.usar_tls,
            'usar_ssl': self.usar_ssl,
            'email_remetente': self.email_remetente,
            'nome_remetente': self.nome_remetente,
            'timeout': self.timeout
        }


class TemplateEmail(models.Model):
    """
    Templates de email com suporte a variáveis dinâmicas
    """
    
    TIPO_TEMPLATE_CHOICES = [
        ('marketing', 'Marketing'),
        ('cobranca', 'Cobrança'),
        ('informativo', 'Informativo'),
        ('promocional', 'Promocional'),
        ('lembrete', 'Lembrete'),
        ('confirmacao', 'Confirmação'),
        ('outro', 'Outro'),
    ]
    
    nome = models.CharField(
        max_length=200,
        verbose_name="Nome do Template",
        help_text="Nome descritivo do template de email"
    )
    
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_TEMPLATE_CHOICES,
        default='informativo',
        verbose_name="Tipo do Template",
        help_text="Categoria do template de email"
    )
    
    assunto = models.CharField(
        max_length=255,
        verbose_name="Assunto do Email",
        help_text="Assunto do email. Suporta variáveis: {{nome_cliente}}, {{valor_fatura}}, etc."
    )
    
    corpo_html = models.TextField(
        verbose_name="Corpo do Email (HTML)",
        help_text="Conteúdo HTML do email. Suporta variáveis como {{nome_cliente}}, {{telefone}}, {{dados_dinamicos.endereco}}, etc."
    )
    
    corpo_texto = models.TextField(
        blank=True,
        verbose_name="Corpo do Email (Texto Puro)",
        help_text="Versão em texto puro do email (opcional). Suporta as mesmas variáveis do HTML."
    )
    
    css_personalizado = models.TextField(
        blank=True,
        verbose_name="CSS Personalizado",
        help_text="CSS adicional para estilização do email"
    )
    
    variaveis_personalizadas = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Variáveis Personalizadas",
        help_text="Variáveis adicionais específicas deste template em formato: {'var_name': 'valor_padrao'}"
    )
    
    descricao = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada do template e seu uso"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se este template está ativo"
    )
    
    # Estatísticas
    total_enviados = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Emails Enviados"
    )
    
    total_sucessos = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Sucessos"
    )
    
    total_erros = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Erros"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    data_ultimo_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data do Último Envio"
    )
    
    class Meta:
        verbose_name = "Template de Email"
        verbose_name_plural = "Templates de Email"
        ordering = ['nome']
    
    def __str__(self):
        return "{} ({})".format(self.nome, self.get_tipo_display())
    
    def extrair_variaveis_do_template(self):
        """
        Extrai variáveis do template (assunto + corpo) no formato {{variavel}}
        Retorna uma lista de nomes de variáveis encontradas
        """
        conteudo = "{} {} {}".format(self.assunto or '', self.corpo_html or '', self.corpo_texto or '')
        
        # Múltiplos padrões para capturar diferentes formatos
        patterns = [
            # Padrão principal: {{variavel}}
            r'\{\{([a-zA-Z_][a-zA-Z0-9_\.]*)\}\}',
            # Padrão com espaços: {{ variavel }}
            r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_\.]*)\s*\}\}',
        ]
        
        variaveis = set()
        
        for pattern in patterns:
            matches = re.findall(pattern, conteudo, re.IGNORECASE)
            variaveis.update(matches)
        
        # Remove variáveis vazias e limpa espaços
        variaveis = {var.strip() for var in variaveis if var.strip()}
        
        return sorted(list(variaveis))
    
    def renderizar_template(self, dados_cliente):
        """
        Renderiza o template substituindo as variáveis pelos dados do cliente
        """
        # Preparar dados para substituição
        dados = {}
        
        # Dados básicos do cliente
        if isinstance(dados_cliente, ClienteConsultado):
            dados.update(dados_cliente.get_dados_completos())
        elif isinstance(dados_cliente, dict):
            dados.update(dados_cliente)
        
        # Adicionar variáveis personalizadas do template
        if self.variaveis_personalizadas:
            dados.update(self.variaveis_personalizadas)
        
        # Adicionar variáveis de sistema
        agora = datetime.now()
        dados.update({
            'data_atual': agora.strftime('%d/%m/%Y'),
            'hora_atual': agora.strftime('%H:%M'),
            'data_hora_atual': agora.strftime('%d/%m/%Y %H:%M'),
            'ano_atual': agora.year,
            'mes_atual': agora.month,
            'dia_atual': agora.day,
        })
        
        # Função para substituir variáveis
        def substituir_variaveis(texto):
            if not texto:
                return texto
            
            resultado = texto
            
            # Substituir variáveis simples
            for chave, valor in dados.items():
                if valor is not None:
                    # Converter para string se necessário
                    valor_str = str(valor)
                    
                    # Múltiplos padrões para substituição
                    patterns = [
                        f"\\{{\\{{{re.escape(chave)}\\}}\\}}",
                        f"\\{{\\{{\\s*{re.escape(chave)}\\s*\\}}\\}}",
                    ]
                    
                    for pattern in patterns:
                        resultado = re.sub(pattern, valor_str, resultado, flags=re.IGNORECASE)
            
            return resultado
        
        # Renderizar assunto e corpos
        assunto_renderizado = substituir_variaveis(self.assunto)
        corpo_html_renderizado = substituir_variaveis(self.corpo_html)
        corpo_texto_renderizado = substituir_variaveis(self.corpo_texto)
        
        # Aplicar CSS personalizado
        if self.css_personalizado:
            if '<style>' not in corpo_html_renderizado:
                corpo_html_renderizado = "<style>{}</style>\n{}".format(self.css_personalizado, corpo_html_renderizado)
        
        return {
            'assunto': assunto_renderizado,
            'corpo_html': corpo_html_renderizado,
            'corpo_texto': corpo_texto_renderizado
        }
    
    def atualizar_estatisticas(self, sucesso=True):
        """Atualiza as estatísticas do template"""
        self.total_enviados += 1
        if sucesso:
            self.total_sucessos += 1
        else:
            self.total_erros += 1
        self.data_ultimo_envio = timezone.now()
        self.save(update_fields=['total_enviados', 'total_sucessos', 'total_erros', 'data_ultimo_envio'])
    
    def get_taxa_sucesso(self):
        """Retorna a taxa de sucesso em percentual"""
        if self.total_enviados == 0:
            return 0
        return round((self.total_sucessos / self.total_enviados) * 100, 2)


class CampanhaEmail(models.Model):
    """
    Campanha de envio de emails integrada com ConsultaExecucao existente
    REUTILIZA a estrutura de consultas já implementada
    SUPORTA envio para clientes ou leads importados via CSV
    """
    
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('processando', 'Processando Dados'),
        ('agendada', 'Agendada'),
        ('executando', 'Executando'),
        ('pausada', 'Pausada'),
        ('concluida', 'Concluída'),
        ('cancelada', 'Cancelada'),
        ('erro', 'Erro'),
    ]
    
    TIPO_AGENDAMENTO_CHOICES = [
        ('unico', 'Envio Único'),
        ('diario', 'Diário'),
        ('semanal', 'Semanal'),
        ('mensal', 'Mensal'),
        ('personalizado', 'Personalizado (Cron)'),
    ]
    
    DIAS_SEMANA_CHOICES = [
        ('0', 'Domingo'),
        ('1', 'Segunda-feira'),
        ('2', 'Terça-feira'),
        ('3', 'Quarta-feira'),
        ('4', 'Quinta-feira'),
        ('5', 'Sexta-feira'),
        ('6', 'Sábado'),
    ]
    
    TIPO_FONTE_CHOICES = [
        ('clientes', 'Clientes (SQL/Execução)'),
        ('leads', 'Leads (CSV Importado)'),
    ]
    
    nome = models.CharField(
        max_length=255,
        verbose_name="Nome da Campanha",
        help_text="Nome descritivo da campanha de email"
    )
    
    descricao = models.TextField(
        blank=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada da campanha"
    )
    
    # NOVO: Tipo de fonte de dados
    tipo_fonte = models.CharField(
        max_length=20,
        choices=TIPO_FONTE_CHOICES,
        default='clientes',
        verbose_name="Tipo de Fonte",
        help_text="De onde vêm os dados: clientes do sistema ou leads importados"
    )
    
    # NOVO: Base de leads (para campanhas de leads)
    base_leads = models.ForeignKey(
        BaseLeads,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Base de Leads",
        help_text="Base de leads importada (apenas para tipo_fonte='leads')"
    )
    
    template_email = models.ForeignKey(
        TemplateEmail,
        on_delete=models.CASCADE,
        verbose_name="Template de Email",
        help_text="Template que será usado para os emails"
    )
    
    configuracao_servidor = models.ForeignKey(
        ConfiguracaoServidorEmail,
        on_delete=models.CASCADE,
        verbose_name="Configuração do Servidor",
        help_text="Configuração SMTP para envio dos emails"
    )
    
    # Integração com sistema existente (para clientes)
    template_sql = models.ForeignKey(
        TemplateSQL,
        on_delete=models.CASCADE,
        verbose_name="Template SQL",
        help_text="Template SQL para buscar os dados dos clientes",
        null=True,
        blank=True
    )
    
    consulta_execucao = models.ForeignKey(
        ConsultaExecucao,
        on_delete=models.SET_NULL,
        verbose_name="Execução da Consulta",
        help_text="Execução específica da consulta SQL",
        null=True,
        blank=True
    )
    
    # Suporte a variáveis SQL
    valores_variaveis_sql = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        verbose_name="Valores das Variáveis SQL",
        help_text="Valores das variáveis necessárias para executar o template SQL"
    )
    
    # Configurações de integração API
    pular_consulta_api = models.BooleanField(
        default=False,
        verbose_name="Pular Consulta na API",
        help_text="Se marcado, não consultará dados na API Hubsoft. Usará apenas dados do SQL."
    )
    
    credencial_hubsoft = models.ForeignKey(
        'campanhas.CredenciaisHubsoft',
        on_delete=models.SET_NULL,
        verbose_name="Credencial Hubsoft",
        help_text="Credencial para consulta na API (obrigatório se não pular API)",
        null=True,
        blank=True
    )
    
    credencial_banco = models.ForeignKey(
        'campanhas.CredenciaisBancoDados',
        on_delete=models.SET_NULL,
        verbose_name="Credencial do Banco",
        help_text="Credencial para conexão com banco de dados",
        null=True,
        blank=True
    )
    
    # Configurações de envio
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='rascunho',
        verbose_name="Status da Campanha"
    )
    
    # Agendamento
    tipo_agendamento = models.CharField(
        max_length=20,
        choices=TIPO_AGENDAMENTO_CHOICES,
        default='unico',
        verbose_name="Tipo de Agendamento"
    )
    
    data_agendamento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Agendamento",
        help_text="Data e hora para execução (para envio único ou primeira execução)"
    )
    
    expressao_cron = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Expressão Cron",
        help_text="Expressão cron para agendamento personalizado (ex: '0 9 * * 1' = toda segunda às 9h)"
    )
    
    intervalo_recorrencia = models.PositiveIntegerField(
        default=1,
        verbose_name="Intervalo de Recorrência",
        help_text="Intervalo para repetição (ex: 1 = todo dia, 2 = dia sim/dia não)"
    )
    
    data_fim_recorrencia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data Fim da Recorrência",
        help_text="Data limite para parar a recorrência (opcional)"
    )
    
    # Configurações específicas para recorrência
    dias_semana_recorrencia = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Dias da Semana",
        help_text="Dias da semana para execução semanal (ex: '1,3,5' = seg, qua, sex)"
    )
    
    dia_mes_recorrencia = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Dia do Mês",
        help_text="Dia do mês para execução mensal (1-31)"
    )
    
    hora_execucao = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Hora de Execução",
        help_text="Hora específica para execução recorrente"
    )
    
    ativa_recorrencia = models.BooleanField(
        default=True,
        verbose_name="Recorrência Ativa",
        help_text="Se a recorrência está ativa (pode ser pausada temporariamente)"
    )
    
    proxima_execucao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Próxima Execução",
        help_text="Data e hora da próxima execução programada"
    )
    
    # Configurações avançadas
    limite_envios_por_execucao = models.PositiveIntegerField(
        default=0,
        verbose_name="Limite de Envios por Execução",
        help_text="0 = sem limite. Útil para evitar sobrecarga do servidor"
    )
    
    intervalo_entre_envios = models.PositiveIntegerField(
        default=0,
        verbose_name="Intervalo Entre Envios (segundos)",
        help_text="Pausa entre cada envio individual. 0 = sem pausa"
    )
    
    # Filtros adicionais
    filtros_sql_adicionais = models.TextField(
        blank=True,
        verbose_name="Filtros SQL Adicionais",
        help_text="Cláusulas WHERE adicionais para filtrar os resultados"
    )
    
    # Estatísticas
    total_destinatarios = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Destinatários"
    )
    
    total_enviados = models.PositiveIntegerField(
        default=0,
        verbose_name="Total Enviados"
    )
    
    total_sucessos = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Sucessos"
    )
    
    total_erros = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de Erros"
    )
    
    total_pendentes = models.PositiveIntegerField(
        default=0,
        verbose_name="Total Pendentes"
    )
    
    # Controle de execução
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se a campanha está ativa"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    data_atualizacao = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de Atualização"
    )
    
    data_inicio_execucao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Início da Execução"
    )
    
    data_fim_execucao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Fim da Execução"
    )
    
    log_execucao = models.TextField(
        blank=True,
        verbose_name="Log de Execução",
        help_text="Log detalhado das execuções"
    )
    
    class Meta:
        verbose_name = "Campanha de Email"
        verbose_name_plural = "Campanhas de Email"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return "{} - {}".format(self.nome, self.get_status_display())
    
    def clean(self):
        """Validação personalizada do modelo"""
        # Validação de fonte de dados
        if self.tipo_fonte == 'clientes':
            if not self.template_sql and not self.consulta_execucao:
                raise ValidationError("Para campanhas de clientes, é necessário Template SQL ou Execução existente")
        elif self.tipo_fonte == 'leads':
            if not self.base_leads:
                raise ValidationError("Para campanhas de leads, é necessário selecionar uma Base de Leads")
        
        if self.tipo_agendamento == 'personalizado' and not self.expressao_cron:
            raise ValidationError("Expressão cron é obrigatória para agendamento personalizado")
        
        if self.tipo_agendamento != 'unico' and not self.data_agendamento:
            raise ValidationError("Data de agendamento é obrigatória para campanhas recorrentes")
    
    def calcular_proxima_execucao(self):
        """Calcula a próxima data de execução baseada no tipo de agendamento"""
        if self.tipo_agendamento == 'unico':
            return self.data_agendamento
        
        if not self.data_agendamento:
            return None
        
        base_date = self.data_inicio_execucao or self.data_agendamento
        
        if self.tipo_agendamento == 'diario':
            proxima = base_date + timedelta(days=self.intervalo_recorrencia)
        elif self.tipo_agendamento == 'semanal':
            proxima = base_date + timedelta(weeks=self.intervalo_recorrencia)
        elif self.tipo_agendamento == 'mensal':
            # Aproximação: 30 dias por mês
            proxima = base_date + timedelta(days=30 * self.intervalo_recorrencia)
        elif self.tipo_agendamento == 'personalizado' and self.expressao_cron:
            try:
                import croniter
                cron = croniter.croniter(self.expressao_cron, base_date)
                proxima = cron.get_next(ret_type=datetime)
            except:
                return None
        else:
            return None
        
        # Verificar se não passou da data limite
        if self.data_fim_recorrencia and proxima > self.data_fim_recorrencia:
            return None
        
        return proxima
    
    def pode_executar(self):
        """Verifica se a campanha pode ser executada"""
        agora = timezone.now()
        
        return (
            self.ativo and
            self.status in ['agendada', 'pausada'] and
            self.template_email.ativo and
            self.configuracao_servidor.ativo and
            (not self.data_agendamento or self.data_agendamento <= agora) and
            (not self.data_fim_recorrencia or agora <= self.data_fim_recorrencia)
        )
    
    def atualizar_status(self, status, log=None):
        """Atualiza o status da campanha e registra log"""
        self.status = status
        
        if log:
            timestamp = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
            if self.log_execucao:
                self.log_execucao += f"\n{timestamp} - {log}"
            else:
                self.log_execucao = f"{timestamp} - {log}"
        
        # Atualizar datas baseado no status
        if status == 'executando' and not self.data_inicio_execucao:
            self.data_inicio_execucao = timezone.now()
        elif status in ['concluida', 'erro', 'cancelada']:
            self.data_fim_execucao = timezone.now()
            
            # Calcular próxima execução se for recorrente
            if status == 'concluida' and self.tipo_agendamento != 'unico':
                self.proxima_execucao = self.calcular_proxima_execucao()
                if self.proxima_execucao:
                    self.status = 'agendada'  # Volta para agendada
        
        self.save()
    
    def get_progresso_percentual(self):
        """Retorna o percentual de progresso da campanha"""
        if self.total_destinatarios == 0:
            return 0
        
        return round((self.total_enviados / self.total_destinatarios) * 100, 2)
    
    def get_taxa_sucesso(self):
        """Retorna a taxa de sucesso em percentual"""
        if self.total_enviados == 0:
            return 0
        
        return round((self.total_sucessos / self.total_enviados) * 100, 2)
    
    def criar_ou_reutilizar_execucao(self):
        """
        Cria uma nova execução ou reutiliza uma existente para atualizar dados
        SEMPRE atualiza os dados antes do envio
        """
        from campanhas.models import ConsultaExecucao, CredenciaisBancoDados, CredenciaisHubsoft
        
        if not self.template_sql:
            raise ValueError("Template SQL é obrigatório para criar execução")
            
        if not self.credencial_banco:
            raise ValueError("Credencial do banco é obrigatória")
        
        # Para campanhas recorrentes, SEMPRE criar nova execução para dados atualizados
        if self.tipo_agendamento != 'unico' or not self.consulta_execucao:
            # Criar nova execução
            titulo_execucao = f"Email: {self.nome} - {timezone.now().strftime('%d/%m/%Y %H:%M')}"
            
            # Debug: verificar variáveis antes de criar execução
            import logging
            logger = logging.getLogger(__name__)
            
            logger.info(f"Criando execução para campanha: {self.nome}")
            logger.info(f"Template SQL: {self.template_sql.titulo}")
            logger.info(f"Variáveis SQL da campanha: {self.valores_variaveis_sql}")
            
            # DEBUG: Print direto para ver as variáveis
            print(f"🔍 CRIAR_OU_REUTILIZAR_EXECUCAO:")
            print(f"  - Campanha: {self.nome}")
            print(f"  - self.valores_variaveis_sql: {self.valores_variaveis_sql}")
            print(f"  - Tipo: {type(self.valores_variaveis_sql)}")
            print(f"  - Valor a ser passado: {self.valores_variaveis_sql or {}}")
            
            # Verificar se as variáveis estão corretas
            if self.template_sql and self.valores_variaveis_sql:
                variaveis_esperadas = self.template_sql.extrair_variaveis_do_sql()
                logger.info(f"Variáveis esperadas pelo template: {variaveis_esperadas}")
                
                # Verificar se há diferenças
                for var_esperada in variaveis_esperadas:
                    if var_esperada not in self.valores_variaveis_sql:
                        logger.warning(f"Variável esperada '{var_esperada}' não encontrada nas variáveis fornecidas")
            
            execucao = ConsultaExecucao.objects.create(
                titulo=titulo_execucao,
                template_sql=self.template_sql,
                credencial_banco=self.credencial_banco,
                credencial_hubsoft=self.credencial_hubsoft,
                valores_variaveis=self.valores_variaveis_sql or {},
                pular_consulta_api=self.pular_consulta_api
            )
            
            logger.info(f"Execução criada com ID: {execucao.id}")
            
            # DEBUG: Verificar se as variáveis foram salvas na execução
            print(f"✅ EXECUÇÃO CRIADA:")
            print(f"  - ID: {execucao.id}")
            print(f"  - execucao.valores_variaveis: {execucao.valores_variaveis}")
            print(f"  - Tipo: {type(execucao.valores_variaveis)}")
            
            self.consulta_execucao = execucao
            self.save(update_fields=['consulta_execucao'])
            
            return execucao
        else:
            # Reutilizar execução existente (apenas para envio único)
            return self.consulta_execucao
    
    def validar_configuracao(self):
        """
        Valida se a campanha tem todas as configurações necessárias
        """
        erros = []
        
        if not self.template_email:
            erros.append("Template de email é obrigatório")
            
        if not self.configuracao_servidor:
            erros.append("Configuração do servidor SMTP é obrigatória")
        
        # Validação de fonte de dados
        if self.tipo_fonte == 'leads':
            # Validação para leads
            if not self.base_leads:
                erros.append("Base de leads é obrigatória quando a fonte é Leads (CSV)")
        else:
            # Validação para clientes (comportamento original)
            if not self.template_sql and not self.consulta_execucao:
                erros.append("É necessário escolher um Template SQL ou uma Execução existente")
            
            if self.template_sql:
                if not self.credencial_banco:
                    erros.append("Credencial do banco é obrigatória quando usar Template SQL")
                
                if not self.pular_consulta_api and not self.credencial_hubsoft:
                    erros.append("Credencial Hubsoft é obrigatória quando consulta API está habilitada")
                
                # Validar variáveis SQL
                if self.template_sql.variaveis_config:
                    variaveis_necessarias = self.template_sql.variaveis_config.keys()
                    variaveis_fornecidas = (self.valores_variaveis_sql or {}).keys()
                    
                    for var in variaveis_necessarias:
                        config = self.template_sql.variaveis_config.get(var, {})
                        if config.get('obrigatorio', True) and var not in variaveis_fornecidas:
                            erros.append(f"Variável SQL obrigatória não fornecida: {var}")
        
        return erros
    
    def obter_clientes_para_envio(self):
        """
        Obtém a lista de clientes com dados atualizados para envio
        SEMPRE garante dados atualizados
        """
        from campanhas.views import processar_consulta_completa
        from campanhas.models import ConsultaCliente
        import threading
        
        # 1. Criar ou reutilizar execução (sempre atualiza dados)
        execucao = self.criar_ou_reutilizar_execucao()
        
        # 2. Se execução não foi processada ou é recorrente, processar agora
        if execucao.status != 'concluida' or self.tipo_agendamento != 'unico':
            self.atualizar_status('executando', 'Atualizando dados dos clientes...')
            
            # Executar processamento em thread separada se necessário
            # Para emails, vamos fazer síncrono para garantir dados atualizados
            processar_consulta_completa(execucao.id)
            
            # Aguardar conclusão
            execucao.refresh_from_db()
            
            if execucao.status != 'concluida':
                raise Exception(f"Falha ao processar dados: {execucao.log_execucao}")
        
        # 3. Obter clientes válidos
        if execucao.pular_consulta_api:
            # Se API foi pulada, considera todos os clientes da execução
            consultas_validas = ConsultaCliente.objects.filter(
                execucao=execucao
            ).select_related('cliente')
        else:
            # Se API foi consultada, considera apenas sucessos
            consultas_validas = ConsultaCliente.objects.filter(
                execucao=execucao,
                sucesso_api=True
            ).select_related('cliente')
        
        # 4. Filtrar apenas clientes com email válido
        clientes_com_email = []
        for consulta in consultas_validas:
            cliente = consulta.cliente
            # Verificar se tem email válido
            dados_completos = cliente.get_dados_completos()
            email = dados_completos.get('email') or ''
            
            if email and '@' in email:
                clientes_com_email.append(cliente)
        
        return clientes_com_email
    
    def obter_leads_para_envio(self):
        """
        Obtém a lista de leads válidos da base importada para envio
        """
        if not self.base_leads:
            return []
        
        # Obter leads válidos da base
        leads = Lead.objects.filter(
            base_leads=self.base_leads,
            valido=True
        ).order_by('linha_original')
        
        return list(leads)
    
    def calcular_proxima_execucao(self, base_datetime=None):
        """
        Calcula a próxima execução baseada no tipo de agendamento
        """
        if self.tipo_agendamento == 'unico':
            return None
            
        if not base_datetime:
            base_datetime = timezone.now()
            
        # Se tem hora específica definida, usar ela
        if self.hora_execucao:
            hora = self.hora_execucao.hour
            minuto = self.hora_execucao.minute
        else:
            hora = base_datetime.hour
            minuto = base_datetime.minute
            
        if self.tipo_agendamento == 'diario':
            proxima = base_datetime.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if proxima <= base_datetime:
                proxima += timedelta(days=self.intervalo_recorrencia)
            return proxima
            
        elif self.tipo_agendamento == 'semanal':
            if self.dias_semana_recorrencia:
                dias_semana = [int(d.strip()) for d in self.dias_semana_recorrencia.split(',')]
                dias_semana.sort()
                
                # Encontrar o próximo dia da semana válido
                dia_atual = base_datetime.weekday()
                # Converter para formato Python (segunda=0)
                dia_atual = (dia_atual + 1) % 7
                
                proxima = None
                for dia_semana in dias_semana:
                    dias_ate_execucao = (dia_semana - dia_atual) % 7
                    if dias_ate_execucao == 0:
                        # É hoje, verificar se ainda não passou da hora
                        candidata = base_datetime.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                        if candidata > base_datetime:
                            proxima = candidata
                            break
                    else:
                        candidata = base_datetime + timedelta(days=dias_ate_execucao)
                        candidata = candidata.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                        if not proxima or candidata < proxima:
                            proxima = candidata
                
                if not proxima:
                    # Nenhum dia válido esta semana, pegar o primeiro da próxima
                    dias_ate_proximo = (dias_semana[0] - dia_atual + 7) % 7
                    if dias_ate_proximo == 0:
                        dias_ate_proximo = 7
                    proxima = base_datetime + timedelta(days=dias_ate_proximo)
                    proxima = proxima.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                
                return proxima
            else:
                # Semanal sem dias específicos, usar o mesmo dia da semana
                proxima = base_datetime.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                if proxima <= base_datetime:
                    proxima += timedelta(weeks=self.intervalo_recorrencia)
                return proxima
                
        elif self.tipo_agendamento == 'mensal':
            if self.dia_mes_recorrencia:
                dia_mes = self.dia_mes_recorrencia
            else:
                dia_mes = base_datetime.day
                
            # Tentar no mês atual
            try:
                proxima = base_datetime.replace(day=dia_mes, hour=hora, minute=minuto, second=0, microsecond=0)
                if proxima <= base_datetime:
                    # Já passou, ir para o próximo mês
                    if base_datetime.month == 12:
                        proxima = proxima.replace(year=base_datetime.year + 1, month=1)
                    else:
                        proxima = proxima.replace(month=base_datetime.month + 1)
            except ValueError:
                # Dia não existe no mês (ex: 31 em fevereiro)
                # Ir para o último dia do mês
                if base_datetime.month == 12:
                    proxima = base_datetime.replace(year=base_datetime.year + 1, month=1, day=1)
                else:
                    proxima = base_datetime.replace(month=base_datetime.month + 1, day=1)
                proxima = proxima.replace(hour=hora, minute=minuto, second=0, microsecond=0)
                # Voltar um dia para pegar o último dia do mês anterior
                proxima = proxima - timedelta(days=1)
                
            return proxima
            
        elif self.tipo_agendamento == 'personalizado' and self.expressao_cron:
            try:
                import croniter
                cron = croniter.croniter(self.expressao_cron, base_datetime)
                proxima = cron.get_next(ret_type=datetime)
                return proxima
            except Exception as e:
                print(f"Erro ao calcular próxima execução cron: {e}")
                # Fallback: retornar próxima hora
                return base_datetime + timedelta(hours=1)
                
        return None
    
    def atualizar_proxima_execucao(self):
        """
        Atualiza o campo proxima_execucao baseado na configuração atual
        """
        if self.tipo_agendamento == 'unico':
            self.proxima_execucao = self.data_agendamento
        else:
            self.proxima_execucao = self.calcular_proxima_execucao()
        
        self.save(update_fields=['proxima_execucao'])
        return self.proxima_execucao
    
    def deve_executar_agora(self):
        """
        Verifica se a campanha deve ser executada agora
        """
        agora = timezone.now()
        
        # Verificar se a recorrência está ativa
        if not self.ativa_recorrencia:
            return False
            
        # Verificar se tem próxima execução definida
        if not self.proxima_execucao:
            # Se não tem próxima execução, calcular uma
            self.proxima_execucao = self.calcular_proxima_execucao()
            if self.proxima_execucao:
                self.save(update_fields=['proxima_execucao'])
            else:
                return False
        
        # Verificar se chegou a hora (com margem de 1 minuto)
        if self.proxima_execucao <= agora + timedelta(minutes=1):
            # Verificar se não passou do fim da recorrência
            if self.data_fim_recorrencia and agora > self.data_fim_recorrencia:
                return False
            return True
            
        return False
    
    def marcar_execucao_concluida(self):
        """
        Marca a execução atual como concluída e calcula a próxima
        """
        if self.tipo_agendamento == 'unico':
            # Para envio único, marcar como concluída
            self.status = 'concluida'
            self.proxima_execucao = None
        else:
            # Para recorrentes, calcular próxima execução
            self.proxima_execucao = self.calcular_proxima_execucao()
            self.status = 'agendada'  # Voltar para agendada para próxima execução
            
        self.save(update_fields=['status', 'proxima_execucao'])
    
    def pausar_recorrencia(self):
        """
        Pausa a recorrência da campanha
        """
        self.ativa_recorrencia = False
        self.save(update_fields=['ativa_recorrencia'])
    
    def reativar_recorrencia(self):
        """
        Reativa a recorrência da campanha
        """
        self.ativa_recorrencia = True
        self.atualizar_proxima_execucao()
        self.save(update_fields=['ativa_recorrencia'])


class EnvioEmailIndividual(models.Model):
    """
    Registro individual de cada email enviado
    """
    
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('enviando', 'Enviando'),
        ('enviado', 'Enviado'),
        ('erro', 'Erro'),
        ('cancelado', 'Cancelado'),
    ]
    
    campanha = models.ForeignKey(
        CampanhaEmail,
        on_delete=models.CASCADE,
        related_name='envios_individuais',
        verbose_name="Campanha"
    )
    
    cliente = models.ForeignKey(
        ClienteConsultado,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Cliente"
    )
    
    lead = models.ForeignKey(
        'Lead',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Lead"
    )
    
    email_destinatario = models.EmailField(
        verbose_name="Email do Destinatário",
        help_text="Email para onde foi enviado"
    )
    
    nome_destinatario = models.CharField(
        max_length=255,
        verbose_name="Nome do Destinatário",
        help_text="Nome do destinatário"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        verbose_name="Status"
    )
    
    assunto_enviado = models.CharField(
        max_length=255,
        verbose_name="Assunto Enviado",
        help_text="Assunto do email após processamento das variáveis"
    )
    
    corpo_enviado = models.TextField(
        verbose_name="Corpo Enviado",
        help_text="Corpo do email após processamento das variáveis"
    )
    
    variaveis_utilizadas = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Variáveis Utilizadas",
        help_text="Variáveis que foram utilizadas no envio"
    )
    
    anexos_enviados = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Anexos Enviados",
        help_text="Lista de anexos que foram enviados"
    )
    
    tentativas = models.PositiveIntegerField(
        default=0,
        verbose_name="Tentativas de Envio"
    )
    
    data_agendamento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data de Agendamento"
    )
    
    data_envio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data do Envio"
    )
    
    tempo_envio_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tempo de Envio (ms)",
        help_text="Tempo gasto para enviar o email em milissegundos"
    )
    
    resposta_servidor = models.TextField(
        blank=True,
        verbose_name="Resposta do Servidor",
        help_text="Resposta do servidor SMTP"
    )
    
    erro_detalhado = models.TextField(
        blank=True,
        verbose_name="Erro Detalhado",
        help_text="Detalhes do erro caso ocorra"
    )
    
    message_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Message ID",
        help_text="ID da mensagem retornado pelo servidor"
    )
    
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    
    class Meta:
        verbose_name = "Envio de Email Individual"
        verbose_name_plural = "Envios de Email Individuais"
        ordering = ['-data_envio']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(cliente__isnull=False, lead__isnull=True) |
                    models.Q(cliente__isnull=True, lead__isnull=False)
                ),
                name='cliente_ou_lead'
            )
        ]
        # Removido unique_together pois agora pode ser cliente OU lead
    
    def __str__(self):
        return "{} ({}) - {}".format(self.nome_destinatario, self.email_destinatario, self.get_status_display())
    
    def marcar_enviado(self, message_id=None, resposta_servidor=None, tempo_envio_ms=None):
        """Marca o email como enviado com sucesso"""
        self.status = 'enviado'
        self.data_envio = timezone.now()
        
        if message_id:
            self.message_id = message_id
        if resposta_servidor:
            self.resposta_servidor = resposta_servidor
        if tempo_envio_ms:
            self.tempo_envio_ms = tempo_envio_ms
        
        self.save()
        
        # Atualizar estatísticas da campanha e template
        self.campanha.total_enviados += 1
        self.campanha.total_sucessos += 1
        self.campanha.save(update_fields=['total_enviados', 'total_sucessos'])
        
        self.campanha.template_email.atualizar_estatisticas(sucesso=True)
    
    def marcar_erro(self, erro, resposta_servidor=None, tempo_envio_ms=None):
        """Marca o email como erro"""
        self.status = 'erro'
        self.data_envio = timezone.now()
        self.erro_detalhado = erro
        self.tentativas += 1
        
        if resposta_servidor:
            self.resposta_servidor = resposta_servidor
        if tempo_envio_ms:
            self.tempo_envio_ms = tempo_envio_ms
        
        self.save()
        
        # Atualizar estatísticas da campanha e template
        self.campanha.total_enviados += 1
        self.campanha.total_erros += 1
        self.campanha.save(update_fields=['total_enviados', 'total_erros'])
        
        self.campanha.template_email.atualizar_estatisticas(sucesso=False)


class LogEnvioEmail(models.Model):
    """
    Log detalhado de ações do sistema de envio de emails
    """
    
    NIVEL_CHOICES = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    campanha = models.ForeignKey(
        CampanhaEmail,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Campanha"
    )
    
    envio_individual = models.ForeignKey(
        EnvioEmailIndividual,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Envio Individual"
    )
    
    nivel = models.CharField(
        max_length=20,
        choices=NIVEL_CHOICES,
        default='info',
        verbose_name="Nível do Log"
    )
    
    acao = models.CharField(
        max_length=100,
        verbose_name="Ação",
        help_text="Ação que foi executada"
    )
    
    mensagem = models.TextField(
        verbose_name="Mensagem",
        help_text="Descrição detalhada da ação"
    )
    
    dados_extras = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Dados Extras",
        help_text="Dados adicionais em formato JSON"
    )
    
    data_criacao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Criação"
    )
    
    class Meta:
        verbose_name = "Log de Envio de Email"
        verbose_name_plural = "Logs de Envio de Email"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"{self.get_nivel_display()} - {self.acao} ({self.data_criacao.strftime('%d/%m/%Y %H:%M')})"
    
    @classmethod
    def criar_log(cls, nivel, acao, mensagem, campanha=None, envio_individual=None, dados_extras=None):
        """Método utilitário para criar logs"""
        return cls.objects.create(
            nivel=nivel,
            acao=acao,
            mensagem=mensagem,
            campanha=campanha,
            envio_individual=envio_individual,
            dados_extras=dados_extras or {}
        )