"""
Admin para gerenciamento de notificações
"""
from django.contrib import admin
from .models import TipoNotificacao, ConfiguracaoNotificacao, Notificacao


@admin.register(TipoNotificacao)
class TipoNotificacaoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'codigo', 'categoria', 'cor', 'ativo', 'data_criacao']
    list_filter = ['categoria', 'cor', 'ativo']
    search_fields = ['nome', 'codigo', 'descricao']
    readonly_fields = ['data_criacao']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('codigo', 'nome', 'descricao', 'categoria')
        }),
        ('Aparência', {
            'fields': ('icone', 'cor')
        }),
        ('Status', {
            'fields': ('ativo', 'data_criacao')
        }),
    )


@admin.register(ConfiguracaoNotificacao)
class ConfiguracaoNotificacaoAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'tipo_notificacao', 'ativo', 'enviar_email', 'data_atualizacao']
    list_filter = ['ativo', 'enviar_email', 'tipo_notificacao__categoria']
    search_fields = ['usuario__username', 'tipo_notificacao__nome']
    readonly_fields = ['data_criacao', 'data_atualizacao']
    
    fieldsets = (
        ('Configuração', {
            'fields': ('usuario', 'tipo_notificacao')
        }),
        ('Preferências', {
            'fields': ('ativo', 'enviar_email')
        }),
        ('Datas', {
            'fields': ('data_criacao', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'usuario', 'tipo_notificacao', 'lida', 'data_criacao', 'data_leitura']
    list_filter = ['lida', 'tipo_notificacao__categoria', 'data_criacao']
    search_fields = ['titulo', 'mensagem', 'usuario__username']
    readonly_fields = ['data_criacao', 'data_leitura']
    date_hierarchy = 'data_criacao'
    
    fieldsets = (
        ('Destinatário', {
            'fields': ('usuario', 'tipo_notificacao')
        }),
        ('Conteúdo', {
            'fields': ('titulo', 'mensagem', 'url')
        }),
        ('Aparência', {
            'fields': ('icone', 'cor')
        }),
        ('Relacionamento', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Dados Adicionais', {
            'fields': ('dados_extras',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('lida', 'data_leitura', 'data_criacao', 'data_expiracao')
        }),
    )
    
    actions = ['marcar_como_lida', 'marcar_como_nao_lida']
    
    def marcar_como_lida(self, request, queryset):
        count = 0
        for notif in queryset:
            if not notif.lida:
                notif.marcar_como_lida()
                count += 1
        self.message_user(request, f'{count} notificação(ões) marcada(s) como lida(s).')
    marcar_como_lida.short_description = 'Marcar como lida'
    
    def marcar_como_nao_lida(self, request, queryset):
        count = 0
        for notif in queryset:
            if notif.lida:
                notif.marcar_como_nao_lida()
                count += 1
        self.message_user(request, f'{count} notificação(ões) marcada(s) como não lida(s).')
    marcar_como_nao_lida.short_description = 'Marcar como não lida'
