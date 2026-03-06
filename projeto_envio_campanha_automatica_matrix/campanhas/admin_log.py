"""
Admin customizado para logs de API
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models_log import APILog, APILogEstatistica


@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'data_hora_formatada', 'status_colored', 'metodo', 
        'endpoint_resumido', 'status_code', 'usuario_display', 
        'tempo_processamento_ms', 'ip_address'
    )
    list_filter = (
        'status', 'metodo', 'status_code', 'usuario_anonimo', 
        'ambiente', 'data_hora'
    )
    search_fields = (
        'endpoint', 'path_completo', 'ip_address', 
        'erro_mensagem', 'erro_tipo', 'usuario__username'
    )
    readonly_fields = (
        'data_hora', 'usuario', 'usuario_anonimo', 'metodo', 
        'endpoint', 'path_completo', 'ip_address', 'user_agent',
        'query_params', 'request_body_display', 'request_headers',
        'status_code', 'status', 'response_body_display', 'response_size',
        'erro_tipo', 'erro_mensagem', 'erro_traceback_display',
        'tempo_processamento', 'tempo_processamento_ms', 'ambiente'
    )
    date_hierarchy = 'data_hora'
    ordering = ('-data_hora',)
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'data_hora', 'usuario', 'usuario_anonimo', 'ambiente'
            )
        }),
        ('Requisição', {
            'fields': (
                'metodo', 'endpoint', 'path_completo', 
                'query_params', 'request_body_display', 'request_headers'
            )
        }),
        ('Cliente', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Resposta', {
            'fields': (
                'status_code', 'status', 'response_body_display', 'response_size',
                'tempo_processamento', 'tempo_processamento_ms'
            )
        }),
        ('Erro (se houver)', {
            'fields': ('erro_tipo', 'erro_mensagem', 'erro_traceback_display'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Não permite adicionar logs manualmente"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Não permite editar logs"""
        return False
    
    def data_hora_formatada(self, obj):
        """Formata a data/hora"""
        return obj.data_hora.strftime('%d/%m/%Y %H:%M:%S')
    data_hora_formatada.short_description = 'Data/Hora'
    
    def status_colored(self, obj):
        """Status com cor"""
        colors = {
            'sucesso': 'green',
            'erro_cliente': 'orange',
            'erro_servidor': 'red',
            'timeout': 'gray',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'Status'
    
    def endpoint_resumido(self, obj):
        """Endpoint resumido (max 50 chars)"""
        if len(obj.endpoint) > 50:
            return obj.endpoint[:47] + '...'
        return obj.endpoint
    endpoint_resumido.short_description = 'Endpoint'
    
    def usuario_display(self, obj):
        """Display do usuário"""
        if obj.usuario:
            return obj.usuario.get_full_name() or obj.usuario.username
        return '(Anônimo)'
    usuario_display.short_description = 'Usuário'
    
    def request_body_display(self, obj):
        """Request body formatado (sem dados sensíveis)"""
        import json
        body = obj.get_request_body_seguro()
        if body:
            return format_html('<pre>{}</pre>', json.dumps(body, indent=2, ensure_ascii=False))
        return '-'
    request_body_display.short_description = 'Request Body'
    
    def response_body_display(self, obj):
        """Response body formatado (limitado)"""
        import json
        if obj.response_body:
            try:
                body_str = json.dumps(obj.response_body, indent=2, ensure_ascii=False)
                if len(body_str) > 1000:
                    body_str = body_str[:1000] + '\n... (truncado)'
                return format_html('<pre>{}</pre>', body_str)
            except:
                return format_html('<pre>{}</pre>', str(obj.response_body)[:1000])
        return '-'
    response_body_display.short_description = 'Response Body'
    
    def erro_traceback_display(self, obj):
        """Traceback formatado"""
        if obj.erro_traceback:
            return format_html('<pre style="background: #f5f5f5; padding: 10px;">{}</pre>', obj.erro_traceback)
        return '-'
    erro_traceback_display.short_description = 'Traceback'
    
    def changelist_view(self, request, extra_context=None):
        """Adiciona estatísticas ao topo da listagem"""
        extra_context = extra_context or {}
        
        # Estatísticas básicas
        qs = self.get_queryset(request)
        stats = qs.aggregate(
            total=Count('id'),
            total_sucesso=Count('id', filter=models.Q(status='sucesso')),
            total_erro=Count('id', filter=models.Q(status__in=['erro_cliente', 'erro_servidor'])),
            tempo_medio=Avg('tempo_processamento')
        )
        
        extra_context['stats'] = {
            'total': stats['total'],
            'total_sucesso': stats['total_sucesso'],
            'total_erro': stats['total_erro'],
            'taxa_sucesso': round((stats['total_sucesso'] / stats['total'] * 100), 2) if stats['total'] > 0 else 0,
            'tempo_medio_ms': round(stats['tempo_medio'] * 1000, 2) if stats['tempo_medio'] else 0,
        }
        
        return super().changelist_view(request, extra_context)


@admin.register(APILogEstatistica)
class APILogEstatisticaAdmin(admin.ModelAdmin):
    list_display = (
        'data', 'hora_display', 'endpoint_resumido', 'metodo',
        'total_requisicoes', 'taxa_sucesso_display', 
        'tempo_medio_ms_display'
    )
    list_filter = ('data', 'metodo')
    search_fields = ('endpoint',)
    readonly_fields = (
        'data', 'hora', 'endpoint', 'metodo',
        'total_requisicoes', 'total_sucesso', 'total_erro_cliente', 'total_erro_servidor',
        'taxa_sucesso', 'taxa_erro',
        'tempo_medio_processamento', 'tempo_minimo_processamento', 'tempo_maximo_processamento',
        'usuarios_unicos', 'ultima_atualizacao'
    )
    date_hierarchy = 'data'
    ordering = ('-data', '-hora')
    
    def has_add_permission(self, request):
        """Não permite adicionar estatísticas manualmente"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Não permite editar estatísticas"""
        return False
    
    def hora_display(self, obj):
        """Display da hora"""
        if obj.hora is not None:
            return f"{obj.hora:02d}h"
        return "Todo dia"
    hora_display.short_description = 'Hora'
    
    def endpoint_resumido(self, obj):
        """Endpoint resumido (max 50 chars)"""
        if len(obj.endpoint) > 50:
            return obj.endpoint[:47] + '...'
        return obj.endpoint
    endpoint_resumido.short_description = 'Endpoint'
    
    def taxa_sucesso_display(self, obj):
        """Taxa de sucesso formatada"""
        return f"{obj.taxa_sucesso}%"
    taxa_sucesso_display.short_description = 'Taxa Sucesso'
    
    def tempo_medio_ms_display(self, obj):
        """Tempo médio em ms"""
        if obj.tempo_medio_processamento:
            return f"{round(obj.tempo_medio_processamento * 1000, 2)} ms"
        return '-'
    tempo_medio_ms_display.short_description = 'Tempo Médio'


# Importar models para usar no admin
from django.db import models
