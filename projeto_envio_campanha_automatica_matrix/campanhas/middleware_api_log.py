"""
Middleware para logging automático de requisições à API
"""
import time
import json
import traceback
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .models_log import APILog


class APILogMiddleware(MiddlewareMixin):
    """
    Middleware que registra todas as requisições feitas aos endpoints da API
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """Captura dados da requisição e inicia o timer"""
        # Só registra se for endpoint de API
        if not request.path.startswith('/api/'):
            return None
        
        # Marca o início do processamento
        request._api_log_start_time = time.time()
        
        # Captura dados da requisição
        request._api_log_data = {
            'metodo': request.method,
            'endpoint': self._get_endpoint(request.path),
            'path_completo': request.get_full_path(),
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
        }
        
        return None
    
    def process_response(self, request, response):
        """Registra a resposta no banco de dados"""
        # Só registra se for endpoint de API e tiver dados iniciais
        if not hasattr(request, '_api_log_start_time'):
            return response
        
        try:
            # Calcula tempo de processamento
            tempo_processamento = time.time() - request._api_log_start_time
            
            # Determina o status baseado no status code
            status_code = response.status_code
            if 200 <= status_code < 300:
                status = 'sucesso'
            elif 400 <= status_code < 500:
                status = 'erro_cliente'
            elif 500 <= status_code < 600:
                status = 'erro_servidor'
            else:
                status = 'sucesso'  # Fallback
            
            # Captura query params
            query_params = dict(request.GET) if request.GET else None
            
            # Captura request body (com segurança)
            request_body = self._get_request_body(request)
            
            # Captura response body (limitado)
            response_body = self._get_response_body(response)
            
            # Captura headers importantes (sem dados sensíveis)
            request_headers = self._get_safe_headers(request)
            
            # Determina o ambiente
            ambiente = getattr(settings, 'ENVIRONMENT', 'producao')
            
            # Cria o log
            api_log = APILog.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                usuario_anonimo=not request.user.is_authenticated,
                metodo=request._api_log_data['metodo'],
                endpoint=request._api_log_data['endpoint'],
                path_completo=request._api_log_data['path_completo'],
                ip_address=request._api_log_data['ip_address'],
                user_agent=request._api_log_data['user_agent'],
                query_params=query_params,
                request_body=request_body,
                request_headers=request_headers,
                status_code=status_code,
                status=status,
                response_body=response_body,
                response_size=len(response.content) if hasattr(response, 'content') else None,
                tempo_processamento=tempo_processamento,
                ambiente=ambiente
            )
            
            # Adiciona o log_id na resposta (útil para debugging)
            if hasattr(response, 'data') and isinstance(response.data, dict):
                response.data['_api_log_id'] = api_log.id
            
        except Exception as e:
            # Se houver erro ao criar o log, não deve quebrar a requisição
            print(f"Erro ao criar log de API: {str(e)}")
            traceback.print_exc()
        
        return response
    
    def process_exception(self, request, exception):
        """Registra exceções que ocorrem durante o processamento"""
        # Só registra se for endpoint de API e tiver dados iniciais
        if not hasattr(request, '_api_log_start_time'):
            return None
        
        try:
            # Calcula tempo até a exceção
            tempo_processamento = time.time() - request._api_log_start_time
            
            # Captura dados da exceção
            erro_tipo = exception.__class__.__name__
            erro_mensagem = str(exception)
            erro_traceback = traceback.format_exc()
            
            # Captura query params
            query_params = dict(request.GET) if request.GET else None
            
            # Captura request body (com segurança)
            request_body = self._get_request_body(request)
            
            # Captura headers importantes (sem dados sensíveis)
            request_headers = self._get_safe_headers(request)
            
            # Determina o ambiente
            ambiente = getattr(settings, 'ENVIRONMENT', 'producao')
            
            # Cria o log de erro
            APILog.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                usuario_anonimo=not request.user.is_authenticated,
                metodo=request._api_log_data['metodo'],
                endpoint=request._api_log_data['endpoint'],
                path_completo=request._api_log_data['path_completo'],
                ip_address=request._api_log_data['ip_address'],
                user_agent=request._api_log_data['user_agent'],
                query_params=query_params,
                request_body=request_body,
                request_headers=request_headers,
                status_code=500,
                status='erro_servidor',
                erro_tipo=erro_tipo,
                erro_mensagem=erro_mensagem[:1000],  # Limita tamanho
                erro_traceback=erro_traceback[:5000],  # Limita tamanho
                tempo_processamento=tempo_processamento,
                ambiente=ambiente
            )
            
        except Exception as e:
            # Se houver erro ao criar o log, não deve quebrar a requisição
            print(f"Erro ao criar log de exceção de API: {str(e)}")
            traceback.print_exc()
        
        return None  # Retorna None para deixar o Django lidar com a exceção
    
    def _get_endpoint(self, path):
        """Extrai o endpoint limpo (sem IDs e query params)"""
        # Remove /api/ do início
        path = path.replace('/api/', '', 1)
        
        # Remove query params
        path = path.split('?')[0]
        
        # Substitui números (IDs) por placeholder
        import re
        path = re.sub(r'/\d+/', '/{id}/', path)
        path = re.sub(r'/\d+$', '/{id}', path)
        
        return path or '/'
    
    def _get_client_ip(self, request):
        """Obtém o IP real do cliente (considerando proxies)"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _get_request_body(self, request):
        """Captura o body da requisição de forma segura"""
        try:
            # Limita o tamanho do body (max 10KB)
            max_size = 10 * 1024
            
            if request.method in ['POST', 'PUT', 'PATCH']:
                body = None
                
                # Tenta obter o body de diferentes formas
                # 1. Django REST Framework (request.data) - PRIORIDADE
                if hasattr(request, 'data') and request.data is not None:
                    try:
                        # Se for QueryDict, converte para dict
                        if hasattr(request.data, 'dict'):
                            body = request.data.dict()
                        # Se já for dict, usa direto
                        elif isinstance(request.data, dict):
                            body = dict(request.data)
                        # Se for lista, mantém como está
                        elif isinstance(request.data, list):
                            body = request.data
                        else:
                            body = dict(request.data) if request.data else None
                    except Exception:
                        # Se falhar, tenta converter para dict de qualquer forma
                        try:
                            body = dict(request.data)
                        except Exception:
                            body = str(request.data)[:max_size]
                
                # 2. Form data (request.POST)
                elif request.POST:
                    body = dict(request.POST)
                
                # 3. Tenta ler o body diretamente (ÚLTIMA OPÇÃO, pode falhar)
                elif not hasattr(request, '_body_read'):
                    try:
                        # Marca que já tentamos ler o body
                        request._body_read = True
                        
                        if request.content_type == 'application/json':
                            body_str = request.body.decode('utf-8')[:max_size]
                            body = json.loads(body_str) if body_str else None
                        else:
                            body_str = request.body.decode('utf-8')[:max_size]
                            body = {'raw': body_str} if body_str else None
                    except Exception:
                        # Se já foi lido antes, apenas registra que não conseguimos capturar
                        pass
                
                # Remove campos sensíveis
                if body:
                    body = self._remove_sensitive_data(body)
                
                return body
            
            return None
            
        except Exception as e:
            # Retorna None ao invés de um dict com erro, para não poluir os logs
            return None
    
    def _get_response_body(self, response):
        """Captura o body da resposta de forma segura"""
        try:
            # Limita o tamanho (max 10KB)
            max_size = 10 * 1024
            
            if hasattr(response, 'data'):
                # Django REST Framework
                data = response.data
                
                # Se for muito grande, resume
                data_str = json.dumps(data)
                if len(data_str) > max_size:
                    return {
                        'resumo': 'Resposta muito grande para registrar',
                        'tamanho': len(data_str),
                        'tipo': str(type(data))
                    }
                
                return data
            
            # Para respostas não-DRF, não captura (pode ser HTML, etc)
            return None
            
        except Exception as e:
            return {'error': f'Erro ao capturar resposta: {str(e)}'}
    
    def _get_safe_headers(self, request):
        """Captura headers importantes, removendo dados sensíveis"""
        headers_importantes = [
            'HTTP_ACCEPT',
            'HTTP_ACCEPT_LANGUAGE',
            'HTTP_CONTENT_TYPE',
            'HTTP_ORIGIN',
            'HTTP_REFERER',
        ]
        
        safe_headers = {}
        for header in headers_importantes:
            value = request.META.get(header)
            if value:
                safe_headers[header.replace('HTTP_', '').lower()] = value[:200]
        
        return safe_headers
    
    def _remove_sensitive_data(self, data):
        """Remove dados sensíveis do dicionário"""
        campos_sensiveis = [
            'password', 'senha', 'token', 'api_key', 'secret', 
            'authorization', 'auth', 'credit_card', 'cartao',
            'cpf', 'cnpj', 'rg'
        ]
        
        if isinstance(data, dict):
            safe_data = {}
            for key, value in data.items():
                # Verifica se a chave é sensível
                if any(campo in key.lower() for campo in campos_sensiveis):
                    safe_data[key] = '***OCULTO***'
                elif isinstance(value, dict):
                    safe_data[key] = self._remove_sensitive_data(value)
                elif isinstance(value, list):
                    safe_data[key] = [
                        self._remove_sensitive_data(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    safe_data[key] = value
            return safe_data
        
        return data
