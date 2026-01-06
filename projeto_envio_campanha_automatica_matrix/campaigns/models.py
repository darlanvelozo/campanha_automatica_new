"""
Models para o sistema de automação de campanhas.

Campaign: Armazena configurações de cada campanha
Execution: Registra cada execução de campanha
ExecutionLog: Logs detalhados de cada execução
"""

from django.db import models
from django.utils import timezone


class Campaign(models.Model):
    """
    Model que representa uma campanha de automação.
    Substitui as funções hardcoded do script original.
    """
    
    # Informações básicas
    name = models.CharField(
        'Nome da Campanha',
        max_length=200,
        help_text='Ex: 2 dias vencidos Mega'
    )
    
    description = models.TextField(
        'Descrição',
        blank=True,
        help_text='Descrição opcional da campanha'
    )
    
    # IDs das APIs
    campaign_id = models.IntegerField(
        'ID da Campanha Native',
        help_text='ID da campanha no sistema Native'
    )
    
    template_sql_id = models.IntegerField(
        'ID do Template SQL',
        help_text='ID do template SQL a ser usado'
    )
    
    credencial_banco_id = models.IntegerField(
        'ID da Credencial do Banco',
        help_text='ID da credencial do banco de dados'
    )
    
    credencial_hubsoft_id = models.IntegerField(
        'ID da Credencial Hubsoft',
        null=True,
        blank=True,
        help_text='ID da credencial Hubsoft (opcional se pular_consulta_api = True)'
    )
    
    # Configurações
    valores_variaveis = models.JSONField(
        'Variáveis',
        default=dict,
        help_text='Variáveis dinâmicas em formato JSON. Ex: {"dia1": "2", "dia2": "2"}'
    )
    
    pular_consulta_api = models.BooleanField(
        'Pular Consulta API',
        default=False,
        help_text='Se True, não consulta a API Hubsoft'
    )
    
    # Status
    enabled = models.BooleanField(
        'Ativa',
        default=True,
        help_text='Campanha ativa e disponível para execução'
    )
    
    # Timestamps
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    last_executed_at = models.DateTimeField('Última Execução', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Campanha'
        verbose_name_plural = 'Campanhas'
        ordering = ['name']
        indexes = [
            models.Index(fields=['enabled', '-last_executed_at']),
            models.Index(fields=['campaign_id']),
        ]
    
    def __str__(self):
        return f"{self.name} (ID: {self.campaign_id})"
    
    def get_titulo_execucao(self):
        """Retorna o título para criar a execução na API"""
        return f"Automação native {self.name}"
    
    def has_running_execution(self):
        """
        Verifica se existe uma execução em andamento para esta campanha.
        Retorna True se houver execução com status que indica processamento ativo.
        """
        running_statuses = ['pending', 'running', 'monitoring', 'creating_list', 'updating_campaign']
        return self.executions.filter(status__in=running_statuses).exists()
    
    def get_latest_execution(self):
        """Retorna a execução mais recente desta campanha"""
        return self.executions.order_by('-started_at').first()


class Execution(models.Model):
    """
    Model que registra cada execução de uma campanha.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('running', 'Em Execução'),
        ('monitoring', 'Monitorando'),
        ('creating_list', 'Criando Lista'),
        ('updating_campaign', 'Atualizando Campanha'),
        ('completed', 'Concluída'),
        ('failed', 'Falhou'),
        ('timeout', 'Timeout'),
    ]
    
    # Relacionamento
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='Campanha'
    )
    
    # IDs da API
    execucao_id = models.IntegerField(
        'ID da Execução',
        null=True,
        blank=True,
        help_text='ID da execução criada na API'
    )
    
    lista_id = models.IntegerField(
        'ID da Lista',
        null=True,
        blank=True,
        help_text='ID da lista criada no Native'
    )
    
    # Status e resultados
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    total_records = models.IntegerField(
        'Total de Registros',
        default=0,
        help_text='Número de registros processados'
    )
    
    success = models.BooleanField(
        'Sucesso',
        default=False
    )
    
    error_message = models.TextField(
        'Mensagem de Erro',
        blank=True,
        help_text='Detalhes do erro, se houver'
    )
    
    # Timestamps
    started_at = models.DateTimeField('Iniciado em', auto_now_add=True)
    completed_at = models.DateTimeField('Concluído em', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Execução'
        verbose_name_plural = 'Execuções'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['-started_at']),
            models.Index(fields=['status']),
            models.Index(fields=['campaign', '-started_at']),
        ]
    
    def __str__(self):
        return f"{self.campaign.name} - {self.get_status_display()} ({self.started_at.strftime('%d/%m/%Y %H:%M')})"
    
    def duration(self):
        """Retorna a duração da execução"""
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return delta
        elif self.started_at:
            delta = timezone.now() - self.started_at
            return delta
        return None
    
    def duration_str(self):
        """Retorna a duração em formato legível"""
        duration = self.duration()
        if duration:
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "-"


class ExecutionLog(models.Model):
    """
    Model que armazena logs detalhados de cada execução.
    """
    
    LEVEL_CHOICES = [
        ('INFO', 'Informação'),
        ('WARNING', 'Aviso'),
        ('ERROR', 'Erro'),
    ]
    
    # Relacionamento
    execution = models.ForeignKey(
        Execution,
        on_delete=models.CASCADE,
        related_name='logs',
        verbose_name='Execução'
    )
    
    # Log
    timestamp = models.DateTimeField('Timestamp', auto_now_add=True)
    level = models.CharField('Nível', max_length=10, choices=LEVEL_CHOICES, default='INFO')
    message = models.TextField('Mensagem')
    
    class Meta:
        verbose_name = 'Log de Execução'
        verbose_name_plural = 'Logs de Execução'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['execution', 'timestamp']),
        ]
    
    def __str__(self):
        return f"[{self.level}] {self.timestamp.strftime('%H:%M:%S')} - {self.message[:50]}"
