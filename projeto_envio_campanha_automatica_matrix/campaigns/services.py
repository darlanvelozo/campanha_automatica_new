"""
Serviço de automação de campanhas.
Baseado na classe AutomacaoCampanha do script original.
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.utils import timezone

from .models import Campaign, Execution, ExecutionLog
from .api_client import NativeAPIClient, CampaignAPIClient


class CampaignAutomationService:
    """
    Serviço principal para automação de campanhas.
    Gerencia todo o fluxo desde a criação da execução até a atualização da campanha.
    """
    
    def __init__(self, execution: Execution):
        """
        Inicializa o serviço de automação.
        
        Args:
            execution: Instância de Execution para registrar logs e status
        """
        self.execution = execution
        self.campaign = execution.campaign
        self.native_client = NativeAPIClient()
        self.campaign_client = CampaignAPIClient()
        self.monitoring_interval = settings.CAMPAIGN_MONITORING_INTERVAL
        self.timeout_minutes = settings.CAMPAIGN_TIMEOUT_MINUTES
    
    def log(self, message: str, level: str = "INFO"):
        """
        Registra uma mensagem de log.
        
        Args:
            message: Mensagem para log
            level: Nível do log (INFO, WARNING, ERROR)
        """
        ExecutionLog.objects.create(
            execution=self.execution,
            level=level,
            message=message
        )
        print(f"[{level}] {message}")
    
    def update_status(self, status: str):
        """Atualiza o status da execução"""
        self.execution.status = status
        self.execution.save(update_fields=['status'])
    
    def create_api_execution(self) -> bool:
        """
        Cria uma execução na API de campanhas.
        
        Returns:
            True se sucesso, False caso contrário
        """
        self.log("Criando execução na API...")
        self.update_status('running')
        
        try:
            # Verificar se a URL da API está configurada
            api_url = settings.CAMPAIGN_API_BASE_URL
            if not api_url or api_url == 'https://api.campanhas.com.br':
                self.log(
                    f"ATENÇÃO: URL da API configurada como '{api_url}'. "
                    f"Verifique se esta URL está correta no settings.py (CAMPAIGN_API_BASE_URL).",
                    "WARNING"
                )
            
            resultado = self.campaign_client.create_execution(
                titulo=self.campaign.get_titulo_execucao(),
                template_sql_id=self.campaign.template_sql_id,
                credencial_banco_id=self.campaign.credencial_banco_id,
                valores_variaveis=self.campaign.valores_variaveis,
                credencial_hubsoft_id=self.campaign.credencial_hubsoft_id,
                pular_consulta_api=self.campaign.pular_consulta_api,
                iniciar_processamento=True
            )
            
            if resultado:
                # Tenta diferentes formatos de resposta
                execucao_id = None
                if isinstance(resultado, dict):
                    execucao_id = resultado.get('id') or resultado.get('execucao_id') or resultado.get('pk')
                elif isinstance(resultado, (int, str)):
                    execucao_id = int(resultado) if str(resultado).isdigit() else None
                
                if execucao_id:
                    status = resultado.get('status', 'desconhecido') if isinstance(resultado, dict) else 'desconhecido'
                    
                    self.execution.execucao_id = execucao_id
                    self.execution.save(update_fields=['execucao_id'])
                    
                    self.log(f"Execução criada com sucesso! ID: {execucao_id}, Status: {status}")
                    return True
                else:
                    # Log da resposta para debug
                    self.log(
                        f"Falha ao criar execução - resposta inválida. Resposta recebida: {resultado}",
                        "ERROR"
                    )
                    return False
            else:
                self.log("Falha ao criar execução - resposta vazia", "ERROR")
                return False
                
        except Exception as e:
            error_msg = str(e)
            # Mensagem mais clara para erros de conexão
            if "não foi possível resolver" in error_msg.lower() or "failed to resolve" in error_msg.lower():
                self.log(
                    f"{error_msg}\n"
                    f"SOLUÇÃO: Verifique se a URL '{settings.CAMPAIGN_API_BASE_URL}' está correta no settings.py. "
                    f"Se estiver em desenvolvimento local, talvez precise usar 'http://localhost:8000' ou a URL correta do servidor.",
                    "ERROR"
                )
            else:
                self.log(f"Erro ao criar execução: {error_msg}", "ERROR")
            return False
    
    def monitor_execution(self) -> bool:
        """
        Monitora a execução até sua finalização.
        
        Returns:
            True se execução finalizou com sucesso, False caso contrário
        """
        self.log(f"Iniciando monitoramento da execução {self.execution.execucao_id}...")
        self.update_status('monitoring')
        
        inicio = timezone.now()
        timeout = timedelta(minutes=self.timeout_minutes)
        
        # Status que indicam finalização
        status_finalizados = [
            'concluido', 'concluida', 'concluído', 'concluída',
            'finalizado', 'finalizada', 'completed', 'finished', 'success'
        ]
        status_erro = ['erro', 'error', 'failed', 'cancelled', 'cancelado', 'falha']
        status_processando = [
            'pendente', 'processando', 'running', 'em_andamento', 
            'executando', 'em_execucao', 'em_execução'
        ]
        
        while timezone.now() - inicio < timeout:
            status = self.campaign_client.get_execution_status(self.execution.execucao_id)
            
            if status:
                self.log(f"Status da execução: {status}")
                
                # Verifica se finalizou com sucesso
                if status.lower() in status_finalizados:
                    self.log(f"Execução finalizada com sucesso!", "INFO")
                    return True
                
                # Verifica se houve erro
                if status.lower() in status_erro:
                    self.log(f"Execução finalizou com erro: {status}", "ERROR")
                    return False
                
                # Status ainda em processamento
                if status.lower() in status_processando:
                    self.log(f"Execução ainda em processamento. Aguardando...")
                else:
                    self.log(f"Status desconhecido: {status}. Continuando monitoramento...")
            
            # Aguarda antes da próxima verificação
            time.sleep(self.monitoring_interval)
        
        # Timeout atingido
        self.log(f"Timeout atingido após {self.timeout_minutes} minutos", "ERROR")
        self.update_status('timeout')
        return False
    
    def generate_list_content(self) -> List[str]:
        """
        Extrai dados dos clientes da execução e converte para formato de lista.
        
        Returns:
            Lista de strings no formato "DOCUMENTO;NOME;TELEFONE"
        """
        self.log(f"Obtendo dados dos clientes da execução {self.execution.execucao_id}...")
        self.update_status('creating_list')
        
        try:
            registros = self.campaign_client.get_execution_clients(self.execution.execucao_id)
            
            if not registros:
                self.log("Nenhum registro encontrado na execução", "WARNING")
                return []
            
            self.log(f"Total de registros obtidos: {len(registros)}")
            
            linhas = []
            for item in registros:
                if not isinstance(item, dict):
                    continue
                
                cliente = item.get("cliente", {})
                dados_sql = item.get("dados_originais_sql", {})
                
                # Extrai documento (CPF/CNPJ)
                documento = (
                    cliente.get("cpf_cnpj") or
                    dados_sql.get("cpf") or
                    dados_sql.get("CPF") or
                    ""
                )
                
                # Extrai nome
                nome = (
                    cliente.get("nome_razaosocial") or
                    dados_sql.get("nome_razaosocial") or
                    dados_sql.get("Nome") or
                    ""
                )
                
                # Extrai telefone
                telefone = (
                    cliente.get("telefone_corrigido") or
                    dados_sql.get("TelefoneCorrigido") or
                    dados_sql.get("telefone") or
                    ""
                )
                
                # Remove o prefixo 55 do telefone se presente
                if telefone and telefone.startswith("55") and len(telefone) > 2:
                    telefone = telefone[2:]
                
                # Adiciona linha se todos os campos obrigatórios estão presentes
                if documento and nome and telefone:
                    linhas.append(f"{documento};{nome};{telefone}")
            
            self.execution.total_records = len(linhas)
            self.execution.save(update_fields=['total_records'])
            
            self.log(f"Extraídas {len(linhas)} linhas válidas da execução")
            return linhas
            
        except Exception as e:
            self.log(f"Erro ao obter dados da execução: {str(e)}", "ERROR")
            return []
    
    def create_dialer_list(self, contents: List[str]) -> Optional[int]:
        """
        Cria uma lista no Native com o conteúdo fornecido.
        
        Args:
            contents: Lista de strings no formato "DOCUMENTO;NOME;TELEFONE"
        
        Returns:
            ID da lista criada ou None em caso de erro
        """
        nome_lista = f"{self.campaign.get_titulo_execucao()} - {self.execution.execucao_id}"
        
        self.log(f"Criando lista '{nome_lista}' com {len(contents)} registros...")
        
        try:
            lista_criada = self.native_client.create_dialer_list(
                name=nome_lista,
                contents=contents
            )
            
            if lista_criada and lista_criada.get('id'):
                lista_id = lista_criada['id']
                self.execution.lista_id = lista_id
                self.execution.save(update_fields=['lista_id'])
                
                self.log(f"Lista criada com sucesso! ID: {lista_id}")
                return lista_id
            else:
                self.log("Falha ao criar lista", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"Erro ao criar lista: {str(e)}", "ERROR")
            return None
    
    def update_native_campaign(self, lista_id: int, state: str) -> bool:
        """
        Atualiza a campanha no Native com a lista e estado.
        
        Args:
            lista_id: ID da lista criada
            state: Estado da campanha ("RUNNING" ou "STOPPED")
        
        Returns:
            True se sucesso, False caso contrário
        """
        self.log(f"Atualizando campanha {self.campaign.campaign_id} com lista {lista_id} e estado {state}...")
        self.update_status('updating_campaign')
        
        try:
            resultado = self.native_client.update_campaign(
                campaign_id=self.campaign.campaign_id,
                dialer_lists=[lista_id],
                state=state
            )
            
            if resultado:
                self.log(f"Campanha atualizada com sucesso!")
                return True
            else:
                self.log("Falha ao atualizar campanha", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro ao atualizar campanha: {str(e)}", "ERROR")
            return False
    
    def stop_campaign(self) -> bool:
        """
        Para a campanha no Native.
        
        Returns:
            True se sucesso, False caso contrário
        """
        self.log(f"Parando campanha {self.campaign.campaign_id}...")
        
        try:
            resultado = self.native_client.update_campaign(
                campaign_id=self.campaign.campaign_id,
                state="STOPPED"
            )
            
            if resultado:
                self.log(f"Campanha parada com sucesso!")
                return True
            else:
                self.log("Falha ao parar campanha", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro ao parar campanha: {str(e)}", "ERROR")
            return False
    
    def execute(self) -> bool:
        """
        Executa o processo completo de automação.
        
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            self.log("=== INICIANDO AUTOMAÇÃO ===")
            
            # Passo 1: Criar execução
            self.log("=== PASSO 1: Criando execução ===")
            if not self.create_api_execution():
                self.execution.success = False
                self.execution.error_message = "Falha ao criar execução"
                self.execution.status = 'failed'
                self.execution.completed_at = timezone.now()
                self.execution.save()
                return False
            
            # Passo 2: Monitorar execução
            self.log("=== PASSO 2: Monitorando execução ===")
            if not self.monitor_execution():
                self.log("Execução não finalizou com sucesso. Parando campanha...", "WARNING")
                self.stop_campaign()
                
                self.execution.success = False
                self.execution.error_message = "Execução não finalizou com sucesso"
                self.execution.status = 'failed'
                self.execution.completed_at = timezone.now()
                self.execution.save()
                return False
            
            # Passo 3: Obter dados e criar lista
            self.log("=== PASSO 3: Criando lista com dados da execução ===")
            conteudo_lista = self.generate_list_content()
            
            if not conteudo_lista:
                self.log("Nenhum dado válido encontrado. Parando campanha...", "WARNING")
                self.stop_campaign()
                
                self.execution.success = False
                self.execution.error_message = "Nenhum dado válido encontrado na execução"
                self.execution.status = 'failed'
                self.execution.completed_at = timezone.now()
                self.execution.save()
                return False
            
            # Criar lista no Native
            lista_id = self.create_dialer_list(conteudo_lista)
            
            if not lista_id:
                self.log("Falha ao criar lista. Parando campanha...", "ERROR")
                self.stop_campaign()
                
                self.execution.success = False
                self.execution.error_message = "Falha ao criar lista no Native"
                self.execution.status = 'failed'
                self.execution.completed_at = timezone.now()
                self.execution.save()
                return False
            
            # Passo 4: Atualizar campanha e iniciar
            self.log("=== PASSO 4: Atualizando campanha e iniciando ===")
            if not self.update_native_campaign(lista_id, "RUNNING"):
                self.execution.success = False
                self.execution.error_message = "Falha ao atualizar campanha no Native"
                self.execution.status = 'failed'
                self.execution.completed_at = timezone.now()
                self.execution.save()
                return False
            
            # Sucesso!
            self.log("=== AUTOMAÇÃO CONCLUÍDA COM SUCESSO ===")
            self.execution.success = True
            self.execution.status = 'completed'
            self.execution.completed_at = timezone.now()
            self.execution.save()
            
            # Atualizar última execução da campanha
            self.campaign.last_executed_at = timezone.now()
            self.campaign.save(update_fields=['last_executed_at'])
            
            return True
            
        except Exception as e:
            self.log(f"Erro durante automação: {str(e)}", "ERROR")
            self.execution.success = False
            self.execution.error_message = str(e)
            self.execution.status = 'failed'
            self.execution.completed_at = timezone.now()
            self.execution.save()
            return False
