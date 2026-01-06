"""
Configuração do Django Admin para gerenciamento de campanhas.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Campaign, Execution, ExecutionLog


class ExecutionLogInline(admin.TabularInline):
    """Inline para exibir logs de execução"""
    model = ExecutionLog
    extra = 0
    readonly_fields = ('timestamp', 'level', 'message')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ExecutionLog)
class ExecutionLogAdmin(admin.ModelAdmin):
    """Admin para logs de execução"""
    list_display = ('execution', 'timestamp', 'level', 'message_preview')
    list_filter = ('level', 'timestamp')
    search_fields = ('message', 'execution__campaign__name')
    readonly_fields = ('execution', 'timestamp', 'level', 'message')
    date_hierarchy = 'timestamp'
    
    def message_preview(self, obj):
        """Prévia da mensagem"""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Mensagem'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return True


class ExecutionInline(admin.TabularInline):
    """Inline para exibir execuções de uma campanha"""
    model = Execution
    extra = 0
    readonly_fields = ('started_at', 'status', 'success', 'total_records', 'duration_str')
    fields = ('started_at', 'status', 'success', 'total_records', 'duration_str')
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    """Admin para execuções"""
    list_display = (
        'id',
        'campaign_link',
        'status_badge',
        'execucao_id',
        'lista_id',
        'total_records',
        'started_at',
        'duration_str',
        'success_icon'
    )
    list_filter = ('status', 'success', 'started_at', 'campaign')
    search_fields = ('campaign__name', 'execucao_id', 'error_message')
    readonly_fields = (
        'campaign',
        'execucao_id',
        'lista_id',
        'status',
        'total_records',
        'success',
        'error_message',
        'started_at',
        'completed_at',
        'duration_str'
    )
    date_hierarchy = 'started_at'
    inlines = [ExecutionLogInline]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('campaign', 'status', 'success')
        }),
        ('IDs da API', {
            'fields': ('execucao_id', 'lista_id')
        }),
        ('Resultados', {
            'fields': ('total_records', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'completed_at', 'duration_str')
        }),
    )
    
    def campaign_link(self, obj):
        """Link para a campanha"""
        url = reverse('admin:campaigns_campaign_change', args=[obj.campaign.id])
        return format_html('<a href="{}">{}</a>', url, obj.campaign.name)
    campaign_link.short_description = 'Campanha'
    
    def status_badge(self, obj):
        """Badge colorido para o status"""
        colors = {
            'pending': '#6c757d',
            'running': '#007bff',
            'monitoring': '#17a2b8',
            'creating_list': '#ffc107',
            'updating_campaign': '#fd7e14',
            'completed': '#28a745',
            'failed': '#dc3545',
            'timeout': '#6f42c1',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def success_icon(self, obj):
        """Ícone de sucesso/falha"""
        if obj.success:
            return format_html('<span style="color: green; font-size: 18px;">✓</span>')
        elif obj.status in ['failed', 'timeout']:
            return format_html('<span style="color: red; font-size: 18px;">✗</span>')
        else:
            return format_html('<span style="color: gray; font-size: 18px;">○</span>')
    success_icon.short_description = 'Sucesso'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Admin para campanhas"""
    list_display = (
        'name',
        'campaign_id',
        'enabled_icon',
        'template_sql_id',
        'credencial_banco_id',
        'last_executed_at',
        'total_executions'
    )
    list_filter = ('enabled', 'template_sql_id', 'credencial_banco_id', 'pular_consulta_api')
    search_fields = ('name', 'description', 'campaign_id')
    readonly_fields = ('created_at', 'updated_at', 'last_executed_at', 'total_executions')
    inlines = [ExecutionInline]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'description', 'enabled')
        }),
        ('IDs da API', {
            'fields': ('campaign_id', 'template_sql_id', 'credencial_banco_id', 'credencial_hubsoft_id')
        }),
        ('Configurações', {
            'fields': ('valores_variaveis', 'pular_consulta_api')
        }),
        ('Informações de Sistema', {
            'fields': ('created_at', 'updated_at', 'last_executed_at', 'total_executions'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['execute_selected_campaigns', 'enable_campaigns', 'disable_campaigns']
    
    def enabled_icon(self, obj):
        """Ícone de ativo/inativo"""
        if obj.enabled:
            return format_html('<span style="color: green; font-size: 18px;">✓</span>')
        else:
            return format_html('<span style="color: red; font-size: 18px;">✗</span>')
    enabled_icon.short_description = 'Ativa'
    
    def total_executions(self, obj):
        """Total de execuções"""
        count = obj.executions.count()
        if count > 0:
            url = reverse('admin:campaigns_execution_changelist') + f'?campaign__id__exact={obj.id}'
            return format_html('<a href="{}">{} execuções</a>', url, count)
        return '0 execuções'
    total_executions.short_description = 'Total de Execuções'
    
    def execute_selected_campaigns(self, request, queryset):
        """Action para executar campanhas selecionadas"""
        from .tasks import execute_campaign_async
        
        count = 0
        for campaign in queryset.filter(enabled=True):
            execute_campaign_async(campaign.id)
            count += 1
        
        self.message_user(request, f'{count} campanha(s) iniciada(s) com sucesso!')
    execute_selected_campaigns.short_description = 'Executar campanhas selecionadas'
    
    def enable_campaigns(self, request, queryset):
        """Action para ativar campanhas"""
        updated = queryset.update(enabled=True)
        self.message_user(request, f'{updated} campanha(s) ativada(s)!')
    enable_campaigns.short_description = 'Ativar campanhas selecionadas'
    
    def disable_campaigns(self, request, queryset):
        """Action para desativar campanhas"""
        updated = queryset.update(enabled=False)
        self.message_user(request, f'{updated} campanha(s) desativada(s)!')
    disable_campaigns.short_description = 'Desativar campanhas selecionadas'
