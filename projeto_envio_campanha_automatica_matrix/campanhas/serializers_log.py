"""
Serializers para os logs de API
"""
from rest_framework import serializers
from .models_log import APILog, APILogEstatistica


class APILogSerializer(serializers.ModelSerializer):
    """Serializer para listagem de logs de API"""
    usuario_nome = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tempo_processamento_ms = serializers.FloatField(read_only=True)
    sucesso = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = APILog
        fields = [
            'id',
            'usuario',
            'usuario_nome',
            'usuario_anonimo',
            'metodo',
            'endpoint',
            'path_completo',
            'ip_address',
            'status_code',
            'status',
            'status_display',
            'sucesso',
            'erro_tipo',
            'erro_mensagem',
            'tempo_processamento',
            'tempo_processamento_ms',
            'data_hora',
            'ambiente',
        ]
        read_only_fields = fields
    
    def get_usuario_nome(self, obj):
        """Retorna o nome do usuário"""
        if obj.usuario:
            return obj.usuario.get_full_name() or obj.usuario.username
        return 'Anônimo'


class APILogDetailSerializer(serializers.ModelSerializer):
    """Serializer para detalhes completos de um log de API"""
    usuario_nome = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tempo_processamento_ms = serializers.FloatField(read_only=True)
    sucesso = serializers.BooleanField(read_only=True)
    request_body_seguro = serializers.SerializerMethodField()
    
    class Meta:
        model = APILog
        fields = [
            'id',
            'usuario',
            'usuario_nome',
            'usuario_anonimo',
            'metodo',
            'endpoint',
            'path_completo',
            'ip_address',
            'user_agent',
            'query_params',
            'request_body',
            'request_body_seguro',
            'request_headers',
            'status_code',
            'status',
            'status_display',
            'sucesso',
            'response_body',
            'response_size',
            'erro_tipo',
            'erro_mensagem',
            'erro_traceback',
            'tempo_processamento',
            'tempo_processamento_ms',
            'data_hora',
            'ambiente',
        ]
        read_only_fields = fields
    
    def get_usuario_nome(self, obj):
        """Retorna o nome do usuário"""
        if obj.usuario:
            return obj.usuario.get_full_name() or obj.usuario.username
        return 'Anônimo'
    
    def get_request_body_seguro(self, obj):
        """Retorna o body sem dados sensíveis"""
        return obj.get_request_body_seguro()


class APILogEstatisticaSerializer(serializers.ModelSerializer):
    """Serializer para estatísticas de uso da API"""
    taxa_sucesso = serializers.FloatField(read_only=True)
    taxa_erro = serializers.FloatField(read_only=True)
    tempo_medio_ms = serializers.SerializerMethodField()
    
    class Meta:
        model = APILogEstatistica
        fields = [
            'id',
            'data',
            'hora',
            'endpoint',
            'metodo',
            'total_requisicoes',
            'total_sucesso',
            'total_erro_cliente',
            'total_erro_servidor',
            'taxa_sucesso',
            'taxa_erro',
            'tempo_medio_processamento',
            'tempo_medio_ms',
            'tempo_minimo_processamento',
            'tempo_maximo_processamento',
            'usuarios_unicos',
            'ultima_atualizacao',
        ]
        read_only_fields = fields
    
    def get_tempo_medio_ms(self, obj):
        """Retorna tempo médio em milissegundos"""
        if obj.tempo_medio_processamento:
            return round(obj.tempo_medio_processamento * 1000, 2)
        return None
