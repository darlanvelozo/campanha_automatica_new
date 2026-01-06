from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from django.utils import timezone

from .models import ConsultaExecucao, ConsultaCliente, EnvioHSMMatrix, HSMTemplate, MatrixAPIConfig, EnvioHSMIndividual, ConfiguracaoPagamentoHSM
from .serializers import (
    ConsultaExecucaoListSerializer,
    ConsultaExecucaoDetailSerializer,
    ConsultaExecucaoCreateSerializer,
    ConsultaClienteSerializer,
    EnvioHSMMatrixListSerializer,
    EnvioHSMMatrixDetailSerializer,
    EnvioHSMMatrixCreateSerializer,
    HSMTemplateSerializer,
    MatrixAPIConfigSerializer,
    MatrixAPIConfigDetailSerializer
)


class ConsultaExecucaoViewSet(viewsets.ModelViewSet):
    """
    ViewSet para consulta e criação de execuções
    
    Endpoints disponíveis:
    - GET /api/execucoes/ - Lista todas as execuções
    - POST /api/execucoes/ - Cria uma nova execução
    - GET /api/execucoes/{id}/ - Detalhes de uma execução específica
    - GET /api/execucoes/{id}/clientes/ - Lista clientes de uma execução
    - GET /api/execucoes/{id}/status/ - Status atual da execução
    """
    queryset = ConsultaExecucao.objects.all().order_by('-data_inicio')
    permission_classes = [AllowAny]  # Temporário para teste
    
    def get_serializer_class(self):
        """Retorna o serializer apropriado baseado na ação"""
        if self.action == 'create':
            return ConsultaExecucaoCreateSerializer
        elif self.action == 'retrieve':
            return ConsultaExecucaoDetailSerializer
        return ConsultaExecucaoListSerializer
    
    def get_queryset(self):
        """Otimiza queries baseado na ação"""
        queryset = super().get_queryset()
        
        if self.action == 'retrieve':
            # Para detalhes, inclui relacionamentos
            queryset = queryset.select_related(
                'template_sql', 'credencial_banco', 'credencial_hubsoft'
            ).prefetch_related(
                Prefetch(
                    'consultacliente_set',
                    queryset=ConsultaCliente.objects.select_related('cliente').order_by('-data_consulta')
                )
            )
        else:
            # Para listagem, apenas relacionamentos básicos
            queryset = queryset.select_related('template_sql', 'credencial_banco')
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def clientes(self, request, pk=None):
        """
        Endpoint para listar apenas os clientes de uma execução
        GET /api/execucoes/{id}/clientes/
        """
        execucao = get_object_or_404(ConsultaExecucao, pk=pk)
        consultas = ConsultaCliente.objects.filter(
            execucao=execucao
        ).select_related('cliente').order_by('-data_consulta')
        
        # Paginação
        page = self.paginate_queryset(consultas)
        if page is not None:
            serializer = ConsultaClienteSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ConsultaClienteSerializer(consultas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Endpoint para consultar apenas o status atual da execução
        GET /api/execucoes/{id}/status/
        """
        execucao = get_object_or_404(ConsultaExecucao, pk=pk)
        
        data = {
            'id': execucao.id,
            'titulo': execucao.titulo,
            'status': execucao.status,
            'status_display': execucao.get_status_display(),
            'total_registros_sql': execucao.total_registros_sql,
            'total_consultados_api': execucao.total_consultados_api,
            'total_erros': execucao.total_erros,
            'clientes_processados': execucao.clientes_processados,
            'clientes_com_sucesso': execucao.clientes_com_sucesso,
            'clientes_com_erro': execucao.clientes_com_erro,
            'data_inicio': execucao.data_inicio,
            'data_fim': execucao.data_fim,
            'progresso_percentual': 0
        }
        
        # Calcula progresso se houver registros SQL
        if execucao.total_registros_sql > 0:
            total_processado = execucao.total_consultados_api + execucao.total_erros
            data['progresso_percentual'] = round((total_processado / execucao.total_registros_sql) * 100, 2)
        
        return Response(data)
    
    @action(detail=True, methods=['get'])
    def clientes_sucesso(self, request, pk=None):
        """
        Endpoint para listar apenas os clientes processados com sucesso
        GET /api/execucoes/{id}/clientes_sucesso/
        """
        execucao = get_object_or_404(ConsultaExecucao, pk=pk)
        consultas = ConsultaCliente.objects.filter(
            execucao=execucao,
            sucesso_api=True
        ).select_related('cliente').order_by('-data_consulta')
        
        # Paginação
        page = self.paginate_queryset(consultas)
        if page is not None:
            serializer = ConsultaClienteSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ConsultaClienteSerializer(consultas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def clientes_erro(self, request, pk=None):
        """
        Endpoint para listar apenas os clientes com erro
        GET /api/execucoes/{id}/clientes_erro/
        """
        execucao = get_object_or_404(ConsultaExecucao, pk=pk)
        consultas = ConsultaCliente.objects.filter(
            execucao=execucao,
            sucesso_api=False
        ).select_related('cliente').order_by('-data_consulta')
        
        # Paginação
        page = self.paginate_queryset(consultas)
        if page is not None:
            serializer = ConsultaClienteSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ConsultaClienteSerializer(consultas, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recursos(self, request):
        """
        Endpoint para listar recursos necessários para criar uma execução
        GET /api/execucoes/recursos/
        """
        try:
            from .models import TemplateSQL, CredenciaisBancoDados, CredenciaisHubsoft
            
            # Listar templates SQL ativos com suas variáveis
            templates_sql_obj = TemplateSQL.objects.filter(ativo=True)
            templates_formatados = []
            
            for template in templates_sql_obj:
                try:
                    # Dados básicos do template
                    template_data = {
                        'id': template.id,
                        'titulo': template.titulo or '',
                        'descricao': template.descricao or '',
                        'variaveis': []
                    }
                    
                    # Tentar obter variáveis configuradas do template
                    if hasattr(template, 'get_variaveis_configuradas'):
                        variaveis_config = template.get_variaveis_configuradas()
                        
                        # Formatar variáveis
                        if variaveis_config and isinstance(variaveis_config, dict):
                            for var_name, config in variaveis_config.items():
                                if isinstance(config, dict):
                                    template_data['variaveis'].append({
                                        'nome': var_name,
                                        'label': config.get('label', var_name.replace('_', ' ').title()),
                                        'tipo': config.get('tipo', 'text'),
                                        'obrigatorio': config.get('obrigatorio', True),
                                        'valor_padrao': config.get('valor_padrao', ''),
                                        'opcoes': config.get('opcoes', '').split('\n') if config.get('opcoes') else []
                                    })
                    
                    templates_formatados.append(template_data)
                    
                except Exception as e:
                    # Se houver erro ao processar um template específico, incluir sem variáveis
                    templates_formatados.append({
                        'id': template.id,
                        'titulo': getattr(template, 'titulo', '') or '',
                        'descricao': getattr(template, 'descricao', '') or '',
                        'variaveis': []
                    })
            
            # Listar credenciais de banco ativas
            try:
                credenciais_banco = list(CredenciaisBancoDados.objects.filter(ativo=True).values(
                    'id', 'titulo', 'tipo_banco', 'host', 'porta'
                ))
            except Exception:
                credenciais_banco = []
            
            # Listar credenciais Hubsoft ativas
            try:
                credenciais_hubsoft = list(CredenciaisHubsoft.objects.filter(ativo=True).values(
                    'id', 'titulo', 'url_base', 'username'
                ))
            except Exception:
                credenciais_hubsoft = []
            
            return Response({
                'templates_sql': templates_formatados,
                'credenciais_banco': credenciais_banco,
                'credenciais_hubsoft': credenciais_hubsoft
            })
            
        except Exception as e:
            # Fallback para o comportamento original em caso de erro geral
            try:
                # Tentar retornar pelo menos os dados básicos
                templates_basicos = list(TemplateSQL.objects.filter(ativo=True).values('id', 'titulo', 'descricao'))
                for template in templates_basicos:
                    template['variaveis'] = []
                
                credenciais_banco_basicas = list(CredenciaisBancoDados.objects.filter(ativo=True).values(
                    'id', 'titulo', 'tipo_banco', 'host', 'porta'
                ))
                
                credenciais_hubsoft_basicas = list(CredenciaisHubsoft.objects.filter(ativo=True).values(
                    'id', 'titulo', 'url_base', 'username'
                ))
                
                return Response({
                    'templates_sql': templates_basicos,
                    'credenciais_banco': credenciais_banco_basicas,
                    'credenciais_hubsoft': credenciais_hubsoft_basicas
                })
            except Exception:
                # Se ainda assim falhar, retornar erro
                return Response({
                    'error': 'Erro ao carregar recursos',
                    'message': str(e),
                    'templates_sql': [],
                    'credenciais_banco': [],
                    'credenciais_hubsoft': []
                }, status=500)
    
    @action(detail=False, methods=['get'])
    def template_variaveis(self, request):
        """
        Endpoint para obter variáveis de um template específico
        GET /api/execucoes/template_variaveis/?template_id=1
        """
        template_id = request.query_params.get('template_id')
        if not template_id:
            return Response(
                {'error': 'Parâmetro template_id é obrigatório'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            template = TemplateSQL.objects.get(id=template_id)
            variaveis = template.get_variaveis_configuradas()
            
            return Response({
                'template_id': template.id,
                'template_titulo': template.titulo,
                'variaveis': variaveis
            })
        except TemplateSQL.DoesNotExist:
            return Response(
                {'error': 'Template SQL não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class ConsultaClienteViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consulta individual de clientes
    
    Endpoints disponíveis:
    - GET /api/clientes/ - Lista todos os clientes consultados
    - GET /api/clientes/{id}/ - Detalhes de um cliente específico
    """
    queryset = ConsultaCliente.objects.all().select_related('cliente', 'execucao').order_by('-data_consulta')
    serializer_class = ConsultaClienteSerializer
    permission_classes = [AllowAny]  # Temporário para teste
    
    def get_queryset(self):
        """Permite filtrar por execução via query param"""
        queryset = super().get_queryset()
        
        # Filtro por execução
        execucao_id = self.request.query_params.get('execucao', None)
        if execucao_id is not None:
            queryset = queryset.filter(execucao_id=execucao_id)
        
        # Filtro por sucesso
        sucesso = self.request.query_params.get('sucesso', None)
        if sucesso is not None:
            if sucesso.lower() in ['true', '1']:
                queryset = queryset.filter(sucesso_api=True)
            elif sucesso.lower() in ['false', '0']:
                queryset = queryset.filter(sucesso_api=False)
        
        return queryset


# =============================================================================
# VIEWSETS PARA HSM
# =============================================================================

class EnvioHSMMatrixViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gerenciar envios de HSM
    
    Endpoints disponíveis:
    - GET /api/envios-hsm/ - Lista todos os envios HSM
    - POST /api/envios-hsm/ - Cria um novo envio HSM
    - GET /api/envios-hsm/{id}/ - Detalhes de um envio específico
    - GET /api/envios-hsm/{id}/status/ - Status atual do envio
    - POST /api/envios-hsm/{id}/executar/ - Executa o envio
    - POST /api/envios-hsm/{id}/cancelar/ - Cancela o envio
    """
    queryset = EnvioHSMMatrix.objects.all().order_by('-data_criacao')
    permission_classes = [AllowAny]  # Temporário para teste
    
    def get_serializer_class(self):
        """Retorna o serializer apropriado baseado na ação"""
        if self.action == 'create':
            return EnvioHSMMatrixCreateSerializer
        elif self.action == 'retrieve':
            return EnvioHSMMatrixDetailSerializer
        return EnvioHSMMatrixListSerializer
    
    def get_queryset(self):
        """Otimiza queries baseado na ação"""
        queryset = super().get_queryset()
        
        # Filtros
        status_envio = self.request.query_params.get('status', None)
        if status_envio:
            queryset = queryset.filter(status_envio=status_envio)
        
        execucao_id = self.request.query_params.get('execucao', None)
        if execucao_id:
            queryset = queryset.filter(consulta_execucao_id=execucao_id)
        
        if self.action == 'retrieve':
            # Para detalhes, inclui relacionamentos
            queryset = queryset.select_related(
                'hsm_template', 'matrix_api_config', 'consulta_execucao'
            ).prefetch_related(
                Prefetch(
                    'envios_individuais',
                    queryset=EnvioHSMIndividual.objects.select_related('cliente').order_by('-data_envio')
                )
            )
        else:
            # Para listagem, apenas relacionamentos básicos
            queryset = queryset.select_related('hsm_template', 'matrix_api_config', 'consulta_execucao')
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """
        Endpoint para consultar apenas o status atual do envio HSM
        GET /api/envios-hsm/{id}/status/
        """
        envio = get_object_or_404(EnvioHSMMatrix, pk=pk)
        
        # Calcular progresso
        progresso_percentual = 0.0
        if envio.total_clientes > 0:
            processados = envio.total_enviados + envio.total_erros
            progresso_percentual = round((processados / envio.total_clientes) * 100, 2)
        
        data = {
            'id': envio.id,
            'titulo': envio.titulo,
            'status_envio': envio.status_envio,
            'total_clientes': envio.total_clientes,
            'total_enviados': envio.total_enviados,
            'total_erros': envio.total_erros,
            'total_pendentes': envio.total_pendentes,
            'progresso_percentual': progresso_percentual,
            'data_criacao': envio.data_criacao,
            'data_inicio_envio': envio.data_inicio_envio,
            'data_fim_envio': envio.data_fim_envio
        }
        
        return Response(data)
    
    @action(detail=True, methods=['post'])
    def executar(self, request, pk=None):
        """
        Endpoint para executar um envio HSM
        POST /api/envios-hsm/{id}/executar/
        """
        envio = get_object_or_404(EnvioHSMMatrix, pk=pk)
        
        # Validar se pode executar
        if envio.status_envio not in ['pendente', 'pausado']:
            return Response({
                'error': f'Não é possível executar envio com status "{envio.status_envio}". '
                         f'Status válidos: pendente, pausado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Importar função de processamento
            from .views import processar_envio_hsm_background
            import threading
            
            # Iniciar processamento em background
            thread = threading.Thread(target=processar_envio_hsm_background, args=(envio.id,))
            thread.daemon = True
            thread.start()
            
            return Response({
                'message': 'Envio iniciado com sucesso',
                'envio_id': envio.id,
                'status': 'processando'
            })
            
        except Exception as e:
            return Response({
                'error': f'Erro ao iniciar envio: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def cancelar(self, request, pk=None):
        """
        Endpoint para cancelar um envio HSM
        POST /api/envios-hsm/{id}/cancelar/
        """
        envio = get_object_or_404(EnvioHSMMatrix, pk=pk)
        
        # Validar se pode cancelar
        if envio.status_envio not in ['pendente', 'enviando', 'pausado']:
            return Response({
                'error': f'Não é possível cancelar envio com status "{envio.status_envio}". '
                         f'Status válidos: pendente, enviando, pausado'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Atualizar status
            envio.status_envio = 'cancelado'
            envio.data_fim_envio = timezone.now()
            envio.save()
            
            return Response({
                'message': 'Envio cancelado com sucesso',
                'envio_id': envio.id,
                'status': 'cancelado'
            })
            
        except Exception as e:
            return Response({
                'error': f'Erro ao cancelar envio: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def testar_nome_com_espacos(self, request):
        """
        Endpoint para testar o processamento de nomes com espaços
        POST /api/envios-hsm/testar_nome_com_espacos/
        """
        try:
            from .views import serializar_valor_para_json
            
            # Testes com diferentes tipos de nomes
            nomes_teste = [
                "CARLOS VASCONCELOS",
                "MARIA DA SILVA", 
                "JOÃO PEDRO SANTOS",
                "ANA CAROLINA",
                "JOSÉ",  # sem espaço
                "  NOME COM ESPAÇOS EXTRAS  ",
                "NOME\tCOM\tTABS",
                "NOME\nCOM\nQUEBRAS"
            ]
            
            resultados = []
            for nome in nomes_teste:
                resultado = serializar_valor_para_json(nome)
                resultados.append({
                    'original': nome,
                    'serializado': resultado,
                    'tem_espacos': ' ' in nome,
                    'comprimento_original': len(nome),
                    'comprimento_serializado': len(resultado),
                    'sucesso': bool(resultado and resultado.strip())
                })
            
            return Response({
                'message': 'Teste de serialização de nomes com espaços',
                'total_testes': len(nomes_teste),
                'resultados': resultados,
                'resumo': {
                    'sucessos': sum(1 for r in resultados if r['sucesso']),
                    'falhas': sum(1 for r in resultados if not r['sucesso'])
                }
            })
            
        except Exception as e:
            return Response({
                'error': f'Erro no teste: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def debug_variaveis_utilizadas(self, request):
        """
        Endpoint para debug das variáveis utilizadas em um envio específico
        POST /api/envios-hsm/debug_variaveis_utilizadas/
        Body: {"envio_id": 123}
        """
        try:
            envio_id = request.data.get('envio_id')
            if not envio_id:
                return Response({
                    'error': 'Campo envio_id é obrigatório'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Buscar o envio
            envio = get_object_or_404(EnvioHSMMatrix, pk=envio_id)
            
            # Buscar envios individuais
            envios_individuais = envio.envios_individuais.all()[:5]  # Primeiros 5
            
            debug_info = {
                'envio_id': envio.id,
                'titulo': envio.titulo,
                'total_clientes': envios_individuais.count(),
                'configuracao_variaveis': envio.configuracao_variaveis,
                'clientes_debug': []
            }
            
            for envio_individual in envios_individuais:
                cliente = envio_individual.cliente
                cliente_debug = {
                    'cliente_id': cliente.id,
                    'codigo_cliente': cliente.codigo_cliente,
                    'nome_razaosocial_original': cliente.nome_razaosocial,
                    'variaveis_utilizadas': envio_individual.variaveis_utilizadas,
                    'variaveis_utilizadas_keys': list(envio_individual.variaveis_utilizadas.keys()),
                    'tem_nome_razaosocial': 'nome_razaosocial' in envio_individual.variaveis_utilizadas,
                    'tem_nome_cliente': 'nome_cliente' in envio_individual.variaveis_utilizadas,
                    'valor_nome_razaosocial': envio_individual.variaveis_utilizadas.get('nome_razaosocial', 'NÃO ENCONTRADO'),
                    'valor_nome_cliente': envio_individual.variaveis_utilizadas.get('nome_cliente', 'NÃO ENCONTRADO')
                }
                debug_info['clientes_debug'].append(cliente_debug)
            
            return Response(debug_info)
            
        except Exception as e:
            return Response({
                'error': f'Erro no debug: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class HSMTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consulta de templates HSM
    
    Endpoints disponíveis:
    - GET /api/hsm-templates/ - Lista todos os templates HSM
    - GET /api/hsm-templates/{id}/ - Detalhes de um template específico
    - GET /api/hsm-templates/{id}/variaveis/ - Variáveis do template
    """
    queryset = HSMTemplate.objects.all().order_by('-data_criacao')
    serializer_class = HSMTemplateSerializer
    permission_classes = [AllowAny]  # Temporário para teste
    
    def get_queryset(self):
        """Permite filtrar por status ativo"""
        queryset = super().get_queryset()
        
        # Filtro por status ativo
        ativo = self.request.query_params.get('ativo', None)
        if ativo is not None:
            if ativo.lower() in ['true', '1']:
                queryset = queryset.filter(ativo=True)
            elif ativo.lower() in ['false', '0']:
                queryset = queryset.filter(ativo=False)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def variaveis(self, request, pk=None):
        """
        Endpoint para obter variáveis de um template HSM
        GET /api/hsm-templates/{id}/variaveis/
        """
        template = get_object_or_404(HSMTemplate, pk=pk)
        
        try:
            variaveis = template.get_variaveis_descricao()
            
            # Formatar variáveis para resposta
            variaveis_formatadas = []
            for var_id, var_config in variaveis.items():
                # Verificar se var_config é string ou dict
                if isinstance(var_config, str):
                    # Formato simples: {"1": "nome_cliente"}
                    variaveis_formatadas.append({
                        'id': var_id,
                        'nome': var_config,
                        'obrigatorio': True,
                        'descricao': ''
                    })
                else:
                    # Formato complexo: {"1": {"nome": "nome_cliente", "obrigatorio": true}}
                    variaveis_formatadas.append({
                        'id': var_id,
                        'nome': var_config.get('nome', f'Variável {var_id}'),
                        'obrigatorio': var_config.get('obrigatorio', True),
                        'descricao': var_config.get('descricao', '')
                    })
            
            return Response({
                'template_id': template.id,
                'template_nome': template.nome,
                'hsm_id': template.hsm_id,
                'variaveis': variaveis_formatadas
            })
            
        except Exception as e:
            return Response({
                'error': f'Erro ao obter variáveis: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MatrixAPIConfigViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consulta de configurações da API Matrix
    
    Endpoints disponíveis:
    - GET /api/configuracoes-matrix/ - Lista todas as configurações
    - GET /api/configuracoes-matrix/{id}/ - Detalhes de uma configuração
    - POST /api/configuracoes-matrix/{id}/testar/ - Testa conexão
    """
    queryset = MatrixAPIConfig.objects.all().order_by('-data_criacao')
    permission_classes = [AllowAny]  # Temporário para teste
    
    def get_serializer_class(self):
        """Retorna o serializer apropriado baseado na ação"""
        if self.action == 'retrieve':
            return MatrixAPIConfigDetailSerializer
        return MatrixAPIConfigSerializer
    
    def get_queryset(self):
        """Permite filtrar por status ativo"""
        queryset = super().get_queryset()
        
        # Filtro por status ativo
        ativo = self.request.query_params.get('ativo', None)
        if ativo is not None:
            if ativo.lower() in ['true', '1']:
                queryset = queryset.filter(ativo=True)
            elif ativo.lower() in ['false', '0']:
                queryset = queryset.filter(ativo=False)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def testar(self, request, pk=None):
        """
        Endpoint para testar conexão com a API Matrix
        POST /api/configuracoes-matrix/{id}/testar/
        """
        config = get_object_or_404(MatrixAPIConfig, pk=pk)
        
        try:
            import requests
            
            # Testar conexão básica
            test_url = f"{config.base_url.rstrip('/')}/rest/v1/test"
            headers = {
                'Authorization': config.api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Fazer requisição de teste (timeout de 10 segundos)
            response = requests.get(test_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            return Response({
                'sucesso': True,
                'mensagem': 'Conexão com API Matrix estabelecida com sucesso',
                'status_code': response.status_code,
                'configuracao': {
                    'id': config.id,
                    'nome': config.nome,
                    'base_url': config.base_url
                }
            })
            
        except requests.exceptions.ConnectionError:
            return Response({
                'sucesso': False,
                'mensagem': 'Erro de conexão: Não foi possível conectar com a API Matrix',
                'configuracao': {
                    'id': config.id,
                    'nome': config.nome,
                    'base_url': config.base_url
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except requests.exceptions.Timeout:
            return Response({
                'sucesso': False,
                'mensagem': 'Timeout: A API Matrix demorou muito para responder',
                'configuracao': {
                    'id': config.id,
                    'nome': config.nome,
                    'base_url': config.base_url
                }
            }, status=status.HTTP_408_REQUEST_TIMEOUT)
            
        except requests.exceptions.HTTPError as e:
            return Response({
                'sucesso': False,
                'mensagem': f'Erro HTTP: {str(e)}',
                'status_code': e.response.status_code if hasattr(e, 'response') else None,
                'configuracao': {
                    'id': config.id,
                    'nome': config.nome,
                    'base_url': config.base_url
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'sucesso': False,
                'mensagem': f'Erro interno: {str(e)}',
                'configuracao': {
                    'id': config.id,
                    'nome': config.nome,
                    'base_url': config.base_url
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfiguracaoPagamentoHSMViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consulta de configurações de pagamento HSM
    
    Endpoints disponíveis:
    - GET /api/configuracoes-pagamento-hsm/ - Lista todas as configurações
    - GET /api/configuracoes-pagamento-hsm/{id}/ - Detalhes de uma configuração
    """
    queryset = ConfiguracaoPagamentoHSM.objects.all().order_by('-ativo', 'nome')
    permission_classes = [AllowAny]  # Temporário para teste
    
    def get_serializer_class(self):
        """Retorna o serializer apropriado baseado na ação"""
        from .serializers import ConfiguracaoPagamentoHSMSerializer
        return ConfiguracaoPagamentoHSMSerializer
    
    def get_queryset(self):
        """Permite filtrar por status ativo"""
        queryset = super().get_queryset()
        
        # Filtro por status ativo
        ativo = self.request.query_params.get('ativo', None)
        if ativo is not None:
            if ativo.lower() in ['true', '1']:
                queryset = queryset.filter(ativo=True)
            elif ativo.lower() in ['false', '0']:
                queryset = queryset.filter(ativo=False)
        
        return queryset
