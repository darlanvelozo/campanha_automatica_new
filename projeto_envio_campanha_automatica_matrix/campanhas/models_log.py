"""
Modelos para registro de logs de consumo da API
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json


class APILog(models.Model):
    """
    Registra todas as requisições feitas à API
    """
    METODO_CHOICES = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
        ('OPTIONS', 'OPTIONS'),
        ('HEAD', 'HEAD'),
    ]
    
    STATUS_CHOICES = [
        ('sucesso', 'Sucesso'),
        ('erro_cliente', 'Erro do Cliente (4xx)'),
        ('erro_servidor', 'Erro do Servidor (5xx)'),
        ('timeout', 'Timeout'),
    ]
    
    # Informações da requisição
    usuario = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='api_logs',
        verbose_name='Usuário'
    )
    usuario_anonimo = models.BooleanField(default=False, verbose_name='Usuário Anônimo')
    
    metodo = models.CharField(max_length=10, choices=METODO_CHOICES, verbose_name='Método HTTP')
    endpoint = models.CharField(max_length=500, db_index=True, verbose_name='Endpoint')
    path_completo = models.TextField(verbose_name='Path Completo com Query Params')
    
    # IP e localização
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='Endereço IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    
    # Dados da requisição
    query_params = models.JSONField(null=True, blank=True, verbose_name='Query Parameters')
    request_body = models.JSONField(null=True, blank=True, verbose_name='Request Body')
    request_headers = models.JSONField(null=True, blank=True, verbose_name='Request Headers')
    
    # Resposta
    status_code = models.IntegerField(db_index=True, verbose_name='Status Code HTTP')
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        db_index=True,
        verbose_name='Status'
    )
    response_body = models.JSONField(null=True, blank=True, verbose_name='Response Body')
    response_size = models.IntegerField(null=True, blank=True, verbose_name='Tamanho da Resposta (bytes)')
    
    # Erro (se houver)
    erro_tipo = models.CharField(max_length=200, blank=True, db_index=True, verbose_name='Tipo de Erro')
    erro_mensagem = models.TextField(blank=True, verbose_name='Mensagem de Erro')
    erro_traceback = models.TextField(blank=True, verbose_name='Traceback do Erro')
    
    # Performance
    tempo_processamento = models.FloatField(null=True, blank=True, verbose_name='Tempo de Processamento (segundos)')
    
    # Metadados
    data_hora = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Data/Hora')
    ambiente = models.CharField(
        max_length=20, 
        default='producao',
        choices=[
            ('desenvolvimento', 'Desenvolvimento'),
            ('homologacao', 'Homologação'),
            ('producao', 'Produção'),
        ],
        verbose_name='Ambiente'
    )
    
    class Meta:
        verbose_name = 'Log de API'
        verbose_name_plural = 'Logs de API'
        ordering = ['-data_hora']
        indexes = [
            models.Index(fields=['-data_hora', 'status']),
            models.Index(fields=['usuario', '-data_hora']),
            models.Index(fields=['endpoint', '-data_hora']),
            models.Index(fields=['status_code', '-data_hora']),
        ]
    
    def __str__(self):
        return f"[{self.get_status_display()}] {self.metodo} {self.endpoint} - {self.data_hora.strftime('%d/%m/%Y %H:%M:%S')}"
    
    @property
    def sucesso(self):
        """Retorna se a requisição foi bem-sucedida"""
        return self.status == 'sucesso'
    
    @property
    def tempo_processamento_ms(self):
        """Retorna o tempo de processamento em milissegundos"""
        if self.tempo_processamento:
            return round(self.tempo_processamento * 1000, 2)
        return None
    
    def get_request_body_seguro(self):
        """Retorna o body da requisição sem dados sensíveis"""
        if not self.request_body:
            return None
        
        # Campos sensíveis para ocultar
        campos_sensiveis = [
            'password', 'senha', 'token', 'api_key', 'secret', 
            'authorization', 'auth', 'credit_card', 'cartao'
        ]
        
        body_seguro = self.request_body.copy() if isinstance(self.request_body, dict) else {}
        
        for campo in campos_sensiveis:
            if campo in body_seguro:
                body_seguro[campo] = '***OCULTO***'
        
        return body_seguro


class APILogEstatistica(models.Model):
    """
    Estatísticas agregadas de uso da API por período
    """
    # Período
    data = models.DateField(db_index=True, verbose_name='Data')
    hora = models.IntegerField(null=True, blank=True, verbose_name='Hora (0-23)')
    
    # Endpoint
    endpoint = models.CharField(max_length=500, db_index=True, verbose_name='Endpoint')
    metodo = models.CharField(max_length=10, verbose_name='Método HTTP')
    
    # Estatísticas
    total_requisicoes = models.IntegerField(default=0, verbose_name='Total de Requisições')
    total_sucesso = models.IntegerField(default=0, verbose_name='Total de Sucessos')
    total_erro_cliente = models.IntegerField(default=0, verbose_name='Total de Erros do Cliente')
    total_erro_servidor = models.IntegerField(default=0, verbose_name='Total de Erros do Servidor')
    
    # Performance
    tempo_medio_processamento = models.FloatField(null=True, blank=True, verbose_name='Tempo Médio (segundos)')
    tempo_minimo_processamento = models.FloatField(null=True, blank=True, verbose_name='Tempo Mínimo (segundos)')
    tempo_maximo_processamento = models.FloatField(null=True, blank=True, verbose_name='Tempo Máximo (segundos)')
    
    # Usuários únicos
    usuarios_unicos = models.IntegerField(default=0, verbose_name='Usuários Únicos')
    
    # Metadados
    ultima_atualizacao = models.DateTimeField(auto_now=True, verbose_name='Última Atualização')
    
    class Meta:
        verbose_name = 'Estatística de API'
        verbose_name_plural = 'Estatísticas de API'
        ordering = ['-data', '-hora']
        unique_together = ('data', 'hora', 'endpoint', 'metodo')
        indexes = [
            models.Index(fields=['-data', 'endpoint']),
            models.Index(fields=['-data', '-hora']),
        ]
    
    def __str__(self):
        hora_str = f"{self.hora:02d}h" if self.hora is not None else "Todo dia"
        return f"{self.data.strftime('%d/%m/%Y')} {hora_str} - {self.metodo} {self.endpoint}"
    
    @property
    def taxa_sucesso(self):
        """Retorna a taxa de sucesso em percentual"""
        if self.total_requisicoes > 0:
            return round((self.total_sucesso / self.total_requisicoes) * 100, 2)
        return 0.0
    
    @property
    def taxa_erro(self):
        """Retorna a taxa de erro em percentual"""
        if self.total_requisicoes > 0:
            total_erros = self.total_erro_cliente + self.total_erro_servidor
            return round((total_erros / self.total_requisicoes) * 100, 2)
        return 0.0
