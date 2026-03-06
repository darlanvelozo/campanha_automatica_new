from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    ConsultaExecucaoViewSet, ConsultaClienteViewSet,
    EnvioHSMMatrixViewSet, HSMTemplateViewSet, MatrixAPIConfigViewSet,
    ConfiguracaoPagamentoHSMViewSet
)
from .api_views_log import APILogViewSet, APILogEstatisticaViewSet

# Cria o router e registra as viewsets
router = DefaultRouter()
router.register(r'execucoes', ConsultaExecucaoViewSet, basename='execucao')
router.register(r'clientes', ConsultaClienteViewSet, basename='cliente')

# ViewSets para HSM
router.register(r'envios-hsm', EnvioHSMMatrixViewSet, basename='envio-hsm')
router.register(r'hsm-templates', HSMTemplateViewSet, basename='hsm-template')
router.register(r'configuracoes-matrix', MatrixAPIConfigViewSet, basename='configuracao-matrix')
router.register(r'configuracoes-pagamento-hsm', ConfiguracaoPagamentoHSMViewSet, basename='configuracao-pagamento-hsm')

# ViewSets para Logs de API
router.register(r'logs', APILogViewSet, basename='log')
router.register(r'logs-estatisticas', APILogEstatisticaViewSet, basename='log-estatistica')

urlpatterns = [
    path('', include(router.urls)),
]
