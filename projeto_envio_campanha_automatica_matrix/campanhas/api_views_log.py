"""
ViewSets para consulta de logs de API
"""
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Count, Avg, Min, Max, Q
from django.utils import timezone
from datetime import timedelta

from .models_log import APILog, APILogEstatistica
from .serializers_log import (
    APILogSerializer,
    APILogDetailSerializer,
    APILogEstatisticaSerializer
)


class APILogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consulta de logs de API
    
    Endpoints disponíveis:
    - GET /api/logs/ - Lista todos os logs (paginado)
    - GET /api/logs/{id}/ - Detalhes de um log específico
    - GET /api/logs/resumo/ - Resumo estatístico dos logs
    - GET /api/logs/erros/ - Lista apenas logs com erro
    - GET /api/logs/por_endpoint/ - Agrupa logs por endpoint
    - GET /api/logs/por_usuario/ - Agrupa logs por usuário
    """
    queryset = APILog.objects.all().order_by('-data_hora')
    permission_classes = [IsAdminUser]  # Apenas admins podem ver logs
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['endpoint', 'erro_mensagem', 'ip_address']
    ordering_fields = ['data_hora', 'tempo_processamento', 'status_code']
    
    def get_serializer_class(self):
        """Retorna o serializer apropriado baseado na ação"""
        if self.action == 'retrieve':
            return APILogDetailSerializer
        return APILogSerializer
    
    def get_queryset(self):
        """Aplica filtros customizados"""
        queryset = super().get_queryset()
        
        # Filtro por status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filtro por método HTTP
        metodo = self.request.query_params.get('metodo', None)
        if metodo:
            queryset = queryset.filter(metodo=metodo.upper())
        
        # Filtro por endpoint
        endpoint = self.request.query_params.get('endpoint', None)
        if endpoint:
            queryset = queryset.filter(endpoint__icontains=endpoint)
        
        # Filtro por usuário
        usuario_id = self.request.query_params.get('usuario', None)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        
        # Filtro por período (últimas N horas)
        horas = self.request.query_params.get('ultimas_horas', None)
        if horas:
            try:
                horas_int = int(horas)
                data_inicio = timezone.now() - timedelta(hours=horas_int)
                queryset = queryset.filter(data_hora__gte=data_inicio)
            except ValueError:
                pass
        
        # Filtro por data específica
        data = self.request.query_params.get('data', None)
        if data:
            try:
                from datetime import datetime
                data_obj = datetime.strptime(data, '%Y-%m-%d').date()
                queryset = queryset.filter(data_hora__date=data_obj)
            except ValueError:
                pass
        
        # Filtro por código de status HTTP
        status_code = self.request.query_params.get('status_code', None)
        if status_code:
            try:
                queryset = queryset.filter(status_code=int(status_code))
            except ValueError:
                pass
        
        # Otimização: select_related para usuário
        queryset = queryset.select_related('usuario')
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def resumo(self, request):
        """
        Retorna resumo estatístico dos logs
        GET /api/logs/resumo/
        """
        # Filtrar por período
        queryset = self.filter_queryset(self.get_queryset())
        
        # Estatísticas gerais
        total = queryset.count()
        total_sucesso = queryset.filter(status='sucesso').count()
        total_erro_cliente = queryset.filter(status='erro_cliente').count()
        total_erro_servidor = queryset.filter(status='erro_servidor').count()
        
        # Tempo médio de processamento
        stats = queryset.aggregate(
            tempo_medio=Avg('tempo_processamento'),
            tempo_minimo=Min('tempo_processamento'),
            tempo_maximo=Max('tempo_processamento')
        )
        
        # Top 10 endpoints mais acessados
        top_endpoints = queryset.values('endpoint', 'metodo').annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        # Top 10 endpoints com mais erros
        top_erros = queryset.filter(
            Q(status='erro_cliente') | Q(status='erro_servidor')
        ).values('endpoint', 'metodo').annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        # Usuários mais ativos
        top_usuarios = queryset.exclude(usuario__isnull=True).values(
            'usuario__username', 'usuario__first_name', 'usuario__last_name'
        ).annotate(
            total=Count('id')
        ).order_by('-total')[:10]
        
        # Taxa de sucesso
        taxa_sucesso = round((total_sucesso / total * 100), 2) if total > 0 else 0
        
        return Response({
            'total_requisicoes': total,
            'total_sucesso': total_sucesso,
            'total_erro_cliente': total_erro_cliente,
            'total_erro_servidor': total_erro_servidor,
            'taxa_sucesso': taxa_sucesso,
            'tempo_medio_ms': round(stats['tempo_medio'] * 1000, 2) if stats['tempo_medio'] else 0,
            'tempo_minimo_ms': round(stats['tempo_minimo'] * 1000, 2) if stats['tempo_minimo'] else 0,
            'tempo_maximo_ms': round(stats['tempo_maximo'] * 1000, 2) if stats['tempo_maximo'] else 0,
            'top_endpoints': list(top_endpoints),
            'top_endpoints_com_erros': list(top_erros),
            'top_usuarios': list(top_usuarios),
        })
    
    @action(detail=False, methods=['get'])
    def erros(self, request):
        """
        Lista apenas logs com erro
        GET /api/logs/erros/
        """
        queryset = self.get_queryset().filter(
            Q(status='erro_cliente') | Q(status='erro_servidor')
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def por_endpoint(self, request):
        """
        Agrupa logs por endpoint
        GET /api/logs/por_endpoint/
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        agrupamento = queryset.values('endpoint', 'metodo').annotate(
            total=Count('id'),
            total_sucesso=Count('id', filter=Q(status='sucesso')),
            total_erro=Count('id', filter=Q(status='erro_cliente') | Q(status='erro_servidor')),
            tempo_medio=Avg('tempo_processamento'),
        ).order_by('-total')
        
        # Adiciona taxa de sucesso e converte tempo para ms
        resultado = []
        for item in agrupamento:
            taxa_sucesso = round((item['total_sucesso'] / item['total'] * 100), 2) if item['total'] > 0 else 0
            resultado.append({
                'endpoint': item['endpoint'],
                'metodo': item['metodo'],
                'total': item['total'],
                'total_sucesso': item['total_sucesso'],
                'total_erro': item['total_erro'],
                'taxa_sucesso': taxa_sucesso,
                'tempo_medio_ms': round(item['tempo_medio'] * 1000, 2) if item['tempo_medio'] else 0,
            })
        
        return Response(resultado)
    
    @action(detail=False, methods=['get'])
    def por_usuario(self, request):
        """
        Agrupa logs por usuário
        GET /api/logs/por_usuario/
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Logs de usuários autenticados
        logs_usuarios = queryset.exclude(usuario__isnull=True).values(
            'usuario__id',
            'usuario__username',
            'usuario__first_name',
            'usuario__last_name',
        ).annotate(
            total=Count('id'),
            total_sucesso=Count('id', filter=Q(status='sucesso')),
            total_erro=Count('id', filter=Q(status='erro_cliente') | Q(status='erro_servidor')),
        ).order_by('-total')
        
        # Logs anônimos
        logs_anonimos = queryset.filter(usuario__isnull=True).aggregate(
            total=Count('id'),
            total_sucesso=Count('id', filter=Q(status='sucesso')),
            total_erro=Count('id', filter=Q(status='erro_cliente') | Q(status='erro_servidor')),
        )
        
        resultado = {
            'usuarios_autenticados': list(logs_usuarios),
            'anonimos': logs_anonimos
        }
        
        return Response(resultado)
    
    @action(detail=False, methods=['get'])
    def timeline(self, request):
        """
        Retorna timeline de requisições (agrupadas por hora)
        GET /api/logs/timeline/
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Agrupa por data e hora
        from django.db.models.functions import TruncHour
        
        timeline = queryset.annotate(
            hora=TruncHour('data_hora')
        ).values('hora').annotate(
            total=Count('id'),
            total_sucesso=Count('id', filter=Q(status='sucesso')),
            total_erro=Count('id', filter=Q(status='erro_cliente') | Q(status='erro_servidor')),
            tempo_medio=Avg('tempo_processamento'),
        ).order_by('hora')
        
        # Formata resultado
        resultado = []
        for item in timeline:
            resultado.append({
                'hora': item['hora'].isoformat(),
                'total': item['total'],
                'total_sucesso': item['total_sucesso'],
                'total_erro': item['total_erro'],
                'tempo_medio_ms': round(item['tempo_medio'] * 1000, 2) if item['tempo_medio'] else 0,
            })
        
        return Response(resultado)


class APILogEstatisticaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consulta de estatísticas agregadas de API
    
    Endpoints disponíveis:
    - GET /api/logs-estatisticas/ - Lista estatísticas (paginado)
    - GET /api/logs-estatisticas/{id}/ - Detalhes de uma estatística
    - GET /api/logs-estatisticas/por_dia/ - Agrupa por dia
    """
    queryset = APILogEstatistica.objects.all().order_by('-data', '-hora')
    serializer_class = APILogEstatisticaSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """Aplica filtros customizados"""
        queryset = super().get_queryset()
        
        # Filtro por data
        data = self.request.query_params.get('data', None)
        if data:
            try:
                from datetime import datetime
                data_obj = datetime.strptime(data, '%Y-%m-%d').date()
                queryset = queryset.filter(data=data_obj)
            except ValueError:
                pass
        
        # Filtro por endpoint
        endpoint = self.request.query_params.get('endpoint', None)
        if endpoint:
            queryset = queryset.filter(endpoint__icontains=endpoint)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def por_dia(self, request):
        """
        Agrupa estatísticas por dia (soma das horas)
        GET /api/logs-estatisticas/por_dia/
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Agrupa por data
        agrupamento = queryset.values('data').annotate(
            total_requisicoes=Count('total_requisicoes'),
            total_sucesso=Count('total_sucesso'),
            total_erro_cliente=Count('total_erro_cliente'),
            total_erro_servidor=Count('total_erro_servidor'),
            tempo_medio=Avg('tempo_medio_processamento'),
        ).order_by('-data')
        
        return Response(list(agrupamento))
