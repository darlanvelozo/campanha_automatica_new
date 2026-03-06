"""
Modelos principais do sistema - Notificações
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TipoNotificacao(models.Model):
    """
    Tipos de notificações que podem ser configuradas
    """
    codigo = models.CharField(max_length=100, unique=True, help_text="Código único do tipo")
    nome = models.CharField(max_length=200, help_text="Nome descritivo do tipo")
    descricao = models.TextField(blank=True, help_text="Descrição detalhada")
    categoria = models.CharField(
        max_length=50,
        choices=[
            ('whatsapp', 'WhatsApp'),
            ('email', 'Email'),
            ('native', 'Ligações Native'),
            ('sistema', 'Sistema'),
        ],
        default='sistema'
    )
    icone = models.CharField(max_length=50, default='bell', help_text="Nome do ícone Lucide")
    cor = models.CharField(
        max_length=20,
        choices=[
            ('primary', 'Azul'),
            ('success', 'Verde'),
            ('warning', 'Amarelo'),
            ('danger', 'Vermelho'),
            ('info', 'Ciano'),
        ],
        default='primary'
    )
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Tipo de Notificação'
        verbose_name_plural = 'Tipos de Notificações'
        ordering = ['categoria', 'nome']
    
    def __str__(self):
        return f"{self.get_categoria_display()} - {self.nome}"


class ConfiguracaoNotificacao(models.Model):
    """
    Configurações de notificação por usuário
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='configuracoes_notificacao')
    tipo_notificacao = models.ForeignKey(TipoNotificacao, on_delete=models.CASCADE)
    ativo = models.BooleanField(default=True, help_text="Se este tipo de notificação está ativo para o usuário")
    enviar_email = models.BooleanField(default=False, help_text="Enviar também por email")
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Configuração de Notificação'
        verbose_name_plural = 'Configurações de Notificações'
        unique_together = ['usuario', 'tipo_notificacao']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.tipo_notificacao.nome}"


class Notificacao(models.Model):
    """
    Notificações do sistema
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificacoes')
    tipo_notificacao = models.ForeignKey(TipoNotificacao, on_delete=models.SET_NULL, null=True, blank=True)
    
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField()
    icone = models.CharField(max_length=50, default='bell')
    cor = models.CharField(max_length=20, default='primary')
    
    # Dados adicionais
    url = models.CharField(max_length=500, blank=True, help_text="URL para onde a notificação aponta")
    dados_extras = models.JSONField(null=True, blank=True, help_text="Dados adicionais em JSON")
    
    # Relacionamentos polimórficos (para vincular a qualquer objeto)
    content_type = models.CharField(max_length=100, blank=True, help_text="Tipo de objeto relacionado")
    object_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID do objeto relacionado")
    
    # Status
    lida = models.BooleanField(default=False)
    data_leitura = models.DateTimeField(null=True, blank=True)
    
    # Datas
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_expiracao = models.DateTimeField(null=True, blank=True, help_text="Data de expiração da notificação")
    
    class Meta:
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['usuario', '-data_criacao']),
            models.Index(fields=['usuario', 'lida']),
        ]
    
    def __str__(self):
        return f"{self.usuario.username} - {self.titulo}"
    
    def marcar_como_lida(self):
        """Marca a notificação como lida"""
        if not self.lida:
            self.lida = True
            self.data_leitura = timezone.now()
            self.save(update_fields=['lida', 'data_leitura'])
    
    def marcar_como_nao_lida(self):
        """Marca a notificação como não lida"""
        if self.lida:
            self.lida = False
            self.data_leitura = None
            self.save(update_fields=['lida', 'data_leitura'])
    
    @property
    def tempo_relativo(self):
        """Retorna o tempo relativo da notificação"""
        from django.utils.timesince import timesince
        return timesince(self.data_criacao)
