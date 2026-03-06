"""
Cliente para integração com as APIs externas.
Baseado nas funções do script original main.py
"""

import requests
import json
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from django.conf import settings
from requests.exceptions import ConnectionError, Timeout, RequestException


class NativeAPIClient:
    """Cliente para a API Native"""
    
    def __init__(self):
        self.base_url = settings.NATIVE_API_BASE_URL.rstrip('/')
        self.token = None
    
    def _extract_domain(self, url: str) -> str:
        """
        Extrai apenas o domínio de uma URL completa.
        
        Args:
            url: URL completa (ex: https://api.native.com.br)
        
        Returns:
            Domínio extraído (ex: api.native.com.br)
        """
        try:
            parsed_url = urlparse(url)
            dominio = parsed_url.netloc
            if dominio:
                return dominio
        except Exception:
            pass
        
        # Fallback: remove protocolo manualmente
        dominio = url.replace('https://', '').replace('http://', '').split('/')[0]
        return dominio
    
    def get_token(self, username: str = None, password: str = None) -> Optional[str]:
        """
        Obtém o token de autenticação da API.
        
        Args:
            username: Nome de usuário (usa settings se não fornecido)
            password: Senha (usa settings se não fornecido)
        
        Returns:
            Token de autenticação se bem-sucedido, None caso contrário
        """
        username = username or settings.NATIVE_API_USERNAME
        password = password or settings.NATIVE_API_PASSWORD
        
        url = f'{self.base_url}/token'
        
        payload = {
            "username": username,
            "password": password
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            self.token = data.get("token")
            return self.token
            
        except ConnectionError as e:
            error_msg = str(e)
            if "Failed to resolve" in error_msg or "Name or service not known" in error_msg:
                dominio = self._extract_domain(self.base_url)
                print(f"Erro de conexão ao obter token: Não foi possível resolver o domínio '{dominio}'. Verifique NATIVE_API_BASE_URL no settings.py")
            else:
                print(f"Erro de conexão ao obter token: {error_msg}")
            return None
        except Timeout as e:
            print(f"Timeout ao obter token: A requisição excedeu o tempo limite de 30 segundos.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Erro ao obter token: {e}")
            return None
    
    def create_dialer_list(self, name: str, contents: List[str], enabled: bool = True) -> Optional[Dict]:
        """
        Cria uma lista com conteúdo customizado (DOCUMENTO;NOME;TELEFONE).
        
        Args:
            name: Nome da lista
            contents: Linhas no formato "DOCUMENTO;NOME;TELEFONE"
            enabled: Se a lista está habilitada
        
        Returns:
            Dados da lista criada se bem-sucedido, None caso contrário
        """
        if not self.token:
            self.get_token()
        
        url = f'{self.base_url}/dialerLists'
        
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "name": name,
            "enabled": enabled,
            "listStructure": [
                {"name": "DOCUMENTO", "phone": False, "phoneDefault": False},
                {"name": "NOME", "phone": False, "phoneDefault": False},
                {"name": "TELEFONE", "phone": True, "phoneDefault": True}
            ],
            "contents": contents
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except ConnectionError as e:
            error_msg = str(e)
            if "Failed to resolve" in error_msg or "Name or service not known" in error_msg:
                dominio = self._extract_domain(self.base_url)
                print(f"Erro de conexão ao criar lista: Não foi possível resolver o domínio '{dominio}'. Verifique NATIVE_API_BASE_URL no settings.py")
            else:
                print(f"Erro de conexão ao criar lista: {error_msg}")
            return None
        except Timeout as e:
            print(f"Timeout ao criar lista: A requisição excedeu o tempo limite de 60 segundos.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Erro ao criar lista: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status Code: {e.response.status_code}")
                print(f"Response: {e.response.text}")
            return None
    
    def update_campaign(self, campaign_id: int, dialer_lists: List[int] = None, state: str = None) -> Optional[Dict]:
        """
        Edita uma campanha existente.
        
        Args:
            campaign_id: ID da campanha a ser editada
            dialer_lists: Lista de IDs das listas para associar à campanha
            state: Estado da campanha ("STOPPED" ou "RUNNING")
        
        Returns:
            Dados da campanha editada se bem-sucedido, None caso contrário
        """
        if not self.token:
            self.get_token()
        
        url = f'{self.base_url}/dialerCampaigns/{campaign_id}'
        
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        payload = {}
        
        if dialer_lists is not None:
            payload["dialerLists"] = dialer_lists
        
        if state is not None:
            payload["state"] = state
        
        try:
            response = requests.put(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except ConnectionError as e:
            error_msg = str(e)
            if "Failed to resolve" in error_msg or "Name or service not known" in error_msg:
                dominio = self._extract_domain(self.base_url)
                print(f"Erro de conexão ao editar campanha: Não foi possível resolver o domínio '{dominio}'. Verifique NATIVE_API_BASE_URL no settings.py")
            else:
                print(f"Erro de conexão ao editar campanha: {error_msg}")
            return None
        except Timeout as e:
            print(f"Timeout ao editar campanha: A requisição excedeu o tempo limite de 30 segundos.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Erro ao editar campanha: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status Code: {e.response.status_code}")
                print(f"Response: {e.response.text}")
            return None


class CampaignAPIClient:
    """Cliente para a API de Campanhas"""
    
    def __init__(self):
        self.base_url = settings.CAMPAIGN_API_BASE_URL.rstrip('/')
        if not self.base_url:
            raise ValueError("CAMPAIGN_API_BASE_URL não está configurado no settings.py")
    
    def _extract_domain(self, url: str) -> str:
        """
        Extrai apenas o domínio de uma URL completa.
        
        Args:
            url: URL completa (ex: https://api.campanhas.com.br)
        
        Returns:
            Domínio extraído (ex: api.campanhas.com.br)
        """
        try:
            parsed_url = urlparse(url)
            dominio = parsed_url.netloc
            if dominio:
                return dominio
        except Exception:
            pass
        
        # Fallback: remove protocolo manualmente
        dominio = url.replace('https://', '').replace('http://', '').split('/')[0]
        return dominio
    
    def _build_url(self, endpoint: str) -> str:
        """
        Constrói uma URL completa a partir do endpoint, evitando duplicação de caminhos.
        
        Args:
            endpoint: Endpoint relativo (ex: 'execucoes/' ou 'execucoes/{id}/status/')
        
        Returns:
            URL completa
        """
        # Remove barras iniciais do endpoint
        endpoint = endpoint.lstrip('/')
        
        # Remove barras finais da base_url
        base = self.base_url.rstrip('/')
        
        # Se a base_url já termina com '/execucoes' ou '/execucoes/', 
        # remove 'execucoes/' do início do endpoint para evitar duplicação
        if base.endswith('/execucoes') or base.endswith('/execucoes/'):
            if endpoint.startswith('execucoes/'):
                endpoint = endpoint[10:]  # Remove 'execucoes/'
            elif endpoint == 'execucoes':
                endpoint = ''
        
        # Se endpoint ficou vazio, retorna apenas a base
        if not endpoint:
            return base
        
        # Constrói a URL
        return f"{base}/{endpoint}"
    
    def _is_internal_request(self, url: str) -> bool:
        """
        Verifica se a requisição é para o mesmo servidor (requisição interna).
        
        Args:
            url: URL completa da requisição
        
        Returns:
            True se for requisição interna, False caso contrário
        """
        try:
            parsed_url = urlparse(url)
            api_domain = parsed_url.netloc.lower()
            api_domain_no_port = api_domain.split(':')[0]
            
            # Verificar se o domínio da API está em ALLOWED_HOSTS
            # Isso indica que é uma requisição para o mesmo servidor
            allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
            
            # Se ALLOWED_HOSTS contém '*', todas as requisições são permitidas
            if '*' in allowed_hosts:
                return True
            
            # Verificar se o domínio está na lista de hosts permitidos
            for host in allowed_hosts:
                host_lower = host.lower()
                host_no_port = host_lower.split(':')[0]
                if api_domain_no_port == host_no_port or host_lower == '*':
                    return True
            
            # Verificar também se o domínio base da API corresponde ao domínio base do servidor
            # Comparar apenas o domínio principal (sem subdomínios)
            try:
                from django.contrib.sites.models import Site
                current_site = Site.objects.get_current()
                current_domain = current_site.domain.lower().split(':')[0]
                # Comparar domínios principais (últimas 2 partes: exemplo.com.br)
                api_parts = api_domain_no_port.split('.')
                current_parts = current_domain.split('.')
                if len(api_parts) >= 2 and len(current_parts) >= 2:
                    api_main = '.'.join(api_parts[-2:])
                    current_main = '.'.join(current_parts[-2:])
                    if api_main == current_main:
                        return True
            except Exception:
                pass
            
            return False
        except Exception:
            return False
    
    def _get_headers(self, url: str, base_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Retorna os headers para a requisição, incluindo header especial para requisições internas.
        
        Args:
            url: URL completa da requisição
            base_headers: Headers base (padrão: {'Content-Type': 'application/json'})
        
        Returns:
            Dict com os headers
        """
        if base_headers is None:
            headers = {'Content-Type': 'application/json'}
        else:
            headers = base_headers.copy()
        
        # Se for requisição interna, adicionar header especial
        if self._is_internal_request(url):
            headers['X-Internal-Request'] = 'true'
        
        return headers
    
    def create_execution(self, titulo: str, template_sql_id: int, credencial_banco_id: int,
                        valores_variaveis: Dict[str, str], credencial_hubsoft_id: Optional[int] = None,
                        pular_consulta_api: bool = False, iniciar_processamento: bool = True) -> Dict[str, Any]:
        """
        Cria uma execução na API.
        
        Args:
            titulo: Título da execução
            template_sql_id: ID do template SQL
            credencial_banco_id: ID da credencial do banco
            valores_variaveis: Dicionário com as variáveis e seus valores
            credencial_hubsoft_id: ID da credencial Hubsoft (opcional)
            pular_consulta_api: Se True, não consulta a API Hubsoft
            iniciar_processamento: Se True, inicia o processamento automaticamente
        
        Returns:
            Dict com a resposta da API
        """
        url = self._build_url("execucoes/")
        
        payload = {
            "titulo": titulo,
            "template_sql_id": template_sql_id,
            "credencial_banco_id": credencial_banco_id,
            "valores_variaveis": valores_variaveis,
            "pular_consulta_api": pular_consulta_api,
            "iniciar_processamento": iniciar_processamento
        }
        
        if credencial_hubsoft_id is not None:
            payload["credencial_hubsoft_id"] = credencial_hubsoft_id
        
        headers = self._get_headers(url)
        
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
            
            # Tenta fazer parse do JSON antes de verificar status
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text, "status_code": response.status_code}
            
            # Verifica status HTTP
            if not response.ok:
                error_msg = f"Erro HTTP {response.status_code}: {response.reason}"
                if response_data:
                    error_msg += f" - Resposta: {response_data}"
                raise Exception(error_msg)
            
            return response_data
        except ConnectionError as e:
            # Erro de conexão (DNS, rede, etc)
            error_msg = str(e)
            if "Failed to resolve" in error_msg or "Name or service not known" in error_msg:
                # Extrai apenas o domínio da URL para mensagem mais clara
                dominio = self._extract_domain(self.base_url)
                raise Exception(
                    f"Não foi possível resolver o domínio '{dominio}'. "
                    f"Verifique se a URL '{self.base_url}' está correta no settings.py (CAMPAIGN_API_BASE_URL) e se o servidor está acessível."
                )
            else:
                raise Exception(f"Erro de conexão ao criar execução: {error_msg}")
        except Timeout as e:
            raise Exception(f"Timeout ao criar execução: A requisição excedeu o tempo limite de 30 segundos.")
        except RequestException as e:
            raise Exception(f"Erro ao criar execução: {str(e)}")
    
    def get_execution_status(self, execucao_id: int) -> Optional[str]:
        """
        Verifica o status de uma execução.
        
        Args:
            execucao_id: ID da execução
        
        Returns:
            Status da execução ou None em caso de erro
        """
        url = self._build_url(f"execucoes/{execucao_id}/status/")
        
        headers = self._get_headers(url, {'Accept': 'application/json'})
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            dados = response.json()
            return dados.get('status', 'desconhecido')
        except ConnectionError as e:
            error_msg = str(e)
            if "Failed to resolve" in error_msg or "Name or service not known" in error_msg:
                dominio = self._extract_domain(self.base_url)
                print(f"Erro de conexão ao verificar status: Não foi possível resolver o domínio '{dominio}'. Verifique CAMPAIGN_API_BASE_URL no settings.py")
            else:
                print(f"Erro de conexão ao verificar status: {error_msg}")
            return None
        except Timeout as e:
            print(f"Timeout ao verificar status: A requisição excedeu o tempo limite de 30 segundos.")
            return None
        except RequestException as e:
            print(f"Erro ao verificar status: {e}")
            return None
    
    def get_execution_clients(self, execucao_id: int, page_size: int = 100) -> List[Dict[str, Any]]:
        """
        Obtém os clientes de uma execução com paginação automática.
        
        Args:
            execucao_id: ID da execução
            page_size: Tamanho da página (padrão: 100)
        
        Returns:
            Lista de registros de clientes. Retorna lista vazia em caso de erro.
        """
        url = self._build_url(f"execucoes/{execucao_id}/clientes/")
        headers = self._get_headers(url, {'Accept': 'application/json'})
        params = {'page_size': page_size}
        
        registros = []
        
        while url:
            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                dados = response.json()
                
                # Se vier como lista simples (sem paginação)
                if isinstance(dados, list):
                    registros.extend([i for i in dados if isinstance(i, dict)])
                    break
                
                # Estrutura com paginação
                if isinstance(dados, dict):
                    pagina = []
                    for key in ["results", "dados", "result", "items", "clientes", "registros"]:
                        if key in dados and isinstance(dados[key], list):
                            pagina = [i for i in dados[key] if isinstance(i, dict)]
                            break
                    
                    registros.extend(pagina)
                    
                    # Próxima página
                    next_url = dados.get('next')
                    url = next_url if next_url else None
                    params = None  # Após primeira requisição, next já tem os params
                else:
                    break
                    
            except ConnectionError as e:
                error_msg = str(e)
                if "Failed to resolve" in error_msg or "Name or service not known" in error_msg:
                    dominio = self._extract_domain(self.base_url)
                    print(f"Erro de conexão ao obter clientes: Não foi possível resolver o domínio '{dominio}'. Verifique CAMPAIGN_API_BASE_URL no settings.py")
                else:
                    print(f"Erro de conexão ao obter clientes: {error_msg}")
                break
            except Timeout as e:
                print(f"Timeout ao obter clientes: A requisição excedeu o tempo limite de 30 segundos.")
                break
            except RequestException as e:
                print(f"Erro ao obter clientes: {e}")
                break
        
        return registros
