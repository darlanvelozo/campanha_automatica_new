"""
EXECUTOR INTEGRADO - Aproveitando sistema de consultas existente
Integra CampanhaEmail com o fluxo de ConsultaExecucao
"""

import logging
import threading
from django.utils import timezone
from django.db import transaction
from io import StringIO
from campanhas.views import executar_consulta_sql
from campanhas.models import ConsultaExecucao, ClienteConsultado
from .models import CampanhaEmail, EnvioEmailIndividual, LogEnvioEmail
from .servico_simplificado import ServicoEmailSimplificado

logger = logging.getLogger(__name__)


class ExecutorCampanhaIntegrado:
    """
    Executor que integra com o sistema de consultas existente
    Segue o mesmo padrão do app campanhas
    """
    
    def __init__(self, campanha):
        self.campanha = campanha
        self.servico_email = None
        self.log_buffer = StringIO()
    
    def executar_campanha_completa(self):
        """
        Executa campanha completa seguindo o padrão do sistema existente:
        1. Executa/Reutiliza ConsultaExecucao
        2. Processa dados dos clientes
        3. Envia emails
        4. Registra logs
        """
        try:
            self.campanha.atualizar_status('executando', 'Iniciando execução da campanha de email...')
            self.log("INFO", "Iniciando execução da campanha", f"Campanha: {self.campanha.nome}")
            
            # Configurar serviço de email
            self.servico_email = ServicoEmailSimplificado(self.campanha.configuracao_servidor)
            
            # 1. OBTER DADOS DOS CLIENTES
            dados_clientes = self._obter_dados_clientes_integrado()
            
            if not dados_clientes:
                self.campanha.atualizar_status('erro', 'Nenhum cliente encontrado com email válido')
                self.log("ERROR", "Nenhum cliente encontrado", "Campanha finalizada sem envios")
                return False
            
            self.log("INFO", "Dados dos clientes obtidos", f"{len(dados_clientes)} clientes com email válido")
            
            # 2. CRIAR ENVIOS INDIVIDUAIS
            self._criar_envios_individuais(dados_clientes)
            
            # 3. PROCESSAR ENVIOS
            self._processar_envios()
            
            # 4. FINALIZAR CAMPANHA
            self._finalizar_campanha()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na execução da campanha {self.campanha.id}: {e}")
            self.campanha.atualizar_status('erro', f'Erro na execução: {str(e)}')
            self.log("ERROR", "Erro na execução", str(e))
            return False
    
    def _obter_dados_clientes_integrado(self):
        """
        Obtém dados dos clientes seguindo o padrão do sistema existente
        """
        try:
            if self.campanha.consulta_execucao:
                # CENÁRIO 1: Reutilizar ConsultaExecucao existente
                return self._obter_dados_de_execucao_existente()
            
            elif self.campanha.template_sql:
                # CENÁRIO 2: Criar nova ConsultaExecucao para email
                return self._criar_nova_execucao_para_email()
            
            else:
                self.log("ERROR", "Configuração inválida", "Nem consulta_execucao nem template_sql definidos")
                return []
                
        except Exception as e:
            self.log("ERROR", "Erro ao obter dados", str(e))
            return []
    
    def _obter_dados_de_execucao_existente(self):
        """
        Reutiliza uma ConsultaExecucao já processada
        """
        try:
            execucao = self.campanha.consulta_execucao
            self.log("INFO", "Reutilizando execução", f"ConsultaExecucao ID: {execucao.id}")
            
            # Buscar clientes já consultados através do modelo ConsultaCliente
            from campanhas.models import ConsultaCliente
            consultas_clientes = ConsultaCliente.objects.filter(execucao=execucao)
            clientes = ClienteConsultado.objects.filter(
                consultacliente__in=consultas_clientes
            ).distinct()
            
            dados_clientes = []
            for cliente in clientes:
                dados = cliente.get_dados_completos()
                email = self._extrair_email(dados)
                
                if email:
                    dados['email'] = email
                    dados['email_destinatario'] = email
                    dados['nome_destinatario'] = dados.get('nome_razaosocial', 'Cliente')
                    dados_clientes.append(dados)
            
            self.log("INFO", "Dados extraídos", f"{len(dados_clientes)} clientes com email de {clientes.count()} total")
            return dados_clientes
            
        except Exception as e:
            self.log("ERROR", "Erro ao obter dados de execução existente", str(e))
            return []
    
    def _criar_nova_execucao_para_email(self):
        """
        Cria uma nova ConsultaExecucao especificamente para esta campanha de email
        Segue o mesmo padrão do sistema existente
        """
        try:
            # Obter credenciais de banco para o template SQL
            template_sql = self.campanha.template_sql
            
            # Tentar diferentes formas de obter credenciais
            credencial_banco = None
            if hasattr(template_sql, 'credenciaisBancoDados') and template_sql.credenciaisBancoDados:
                credencial_banco = template_sql.credenciaisBancoDados
            else:
                # Buscar credencial padrão ou primeira disponível
                from campanhas.models import CredenciaisBancoDados
                credencial_banco = CredenciaisBancoDados.objects.filter(ativo=True).first()
            
            if not credencial_banco:
                self.log("ERROR", "Credencial de banco não encontrada", f"Template SQL: {template_sql.titulo}")
                return []
            
            # Criar nova ConsultaExecucao temporária para email COM VARIÁVEIS
            print(f"🔧 CRIANDO EXECUÇÃO COM VARIÁVEIS: {self.campanha.valores_variaveis_sql}")
            execucao = ConsultaExecucao.objects.create(
                titulo=f"Execução Email - {self.campanha.nome}",
                template_sql=template_sql,
                credencial_banco=self.campanha.credencial_banco or credencial_banco,
                credencial_hubsoft=self.campanha.credencial_hubsoft,
                valores_variaveis=self.campanha.valores_variaveis_sql or {},
                pular_consulta_api=self.campanha.pular_consulta_api,
                status='pendente'
            )
            
            self.log("INFO", "Nova execução criada", f"ConsultaExecucao ID: {execucao.id}")
            
            # Executar consulta SQL usando a mesma função do sistema existente
            execucao.atualizar_status('executando', 'Executando consulta SQL para campanha de email')
            
            print(f"🔧 EXECUTANDO SQL COM VARIÁVEIS:")
            print(f"  - execucao.valores_variaveis: {execucao.valores_variaveis}")
            print(f"  - template: {execucao.template_sql.titulo}")
            
            resultados_sql = executar_consulta_sql(
                execucao.credencial_banco,
                execucao.template_sql,
                execucao.valores_variaveis
            )
            
            execucao.total_registros_sql = len(resultados_sql)
            execucao.save()
            
            if not resultados_sql:
                execucao.atualizar_status('erro', 'Nenhum resultado encontrado na consulta SQL')
                self.log("ERROR", "Consulta SQL vazia", "Nenhum resultado retornado")
                return []
            
            # USAR O PROCESSAMENTO COMPLETO DO SISTEMA EXISTENTE
            self.log("INFO", "Iniciando processamento completo", f"Processando {len(resultados_sql)} registros via API")
            
            # Chamar processar_consulta_completa para fazer todo o processamento
            from campanhas.views import processar_consulta_completa
            print(f"🔧 CHAMANDO processar_consulta_completa({execucao.id})")
            processar_consulta_completa(execucao.id)
            
            # Recarregar execução para obter dados atualizados
            execucao.refresh_from_db()
            
            # Obter clientes processados
            from campanhas.models import ConsultaCliente
            consultas_clientes = ConsultaCliente.objects.filter(execucao=execucao)
            clientes = ClienteConsultado.objects.filter(
                consultacliente__in=consultas_clientes
            ).distinct()
            
            dados_clientes = []
            for cliente in clientes:
                dados = cliente.get_dados_completos()
                email = self._extrair_email(dados)
                if email:
                    dados['email'] = email
                    dados['email_destinatario'] = email
                    dados['nome_destinatario'] = dados.get('nome_razaosocial', 'Cliente')
                    dados_clientes.append(dados)
            
            # Vincular execução à campanha
            self.campanha.consulta_execucao = execucao
            self.campanha.save()
            
            execucao.atualizar_status('concluida', f'{len(dados_clientes)} clientes processados para email')
            
            self.log("INFO", "Consulta executada", f"{len(dados_clientes)} clientes com email de {len(resultados_sql)} total")
            return dados_clientes
            
        except Exception as e:
            self.log("ERROR", "Erro ao criar nova execução", str(e))
            return []
    
    def _extrair_email(self, dados):
        """Extrai email dos dados (mesmo padrão do sistema)"""
        campos_email = ['email', 'email_cliente', 'email_contato', 'e_mail']
        
        for campo in campos_email:
            email = dados.get(campo)
            if email and '@' in str(email):
                return str(email).strip()
        
        return None
    
    def _serializar_dados_para_json(self, dados):
        """Converte dados para formato serializável em JSON"""
        import json
        from datetime import date, datetime
        import decimal
        
        def converter_valores(obj):
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            elif isinstance(obj, decimal.Decimal):
                return float(obj)
            elif hasattr(obj, '__dict__'):
                return str(obj)
            else:
                return obj
        
        dados_serializaveis = {}
        for chave, valor in dados.items():
            dados_serializaveis[chave] = converter_valores(valor)
        
        return dados_serializaveis
    
    def _criar_envios_individuais(self, dados_clientes):
        """Cria registros de envios individuais"""
        try:
            self.log("INFO", "Criando envios individuais", f"{len(dados_clientes)} envios")
            
            envios_criados = 0
            for dados in dados_clientes:
                try:
                    # Renderizar template para este cliente
                    email_renderizado = self._renderizar_template(dados)
                    
                    # Buscar ClienteConsultado correspondente
                    cliente_consultado = None
                    codigo_cliente = dados.get('codigo_cliente')
                    if codigo_cliente:
                        from campanhas.models import ConsultaCliente
                        try:
                            consulta_cliente = ConsultaCliente.objects.filter(
                                execucao=self.campanha.consulta_execucao,
                                cliente__codigo_cliente=codigo_cliente
                            ).first()
                            if consulta_cliente:
                                cliente_consultado = consulta_cliente.cliente
                        except:
                            pass
                    
                    # Serializar dados para JSON (converter dates)
                    dados_serializaveis = self._serializar_dados_para_json(dados)
                    
                    # Criar envio individual
                    EnvioEmailIndividual.objects.create(
                        campanha=self.campanha,
                        cliente=cliente_consultado,  # Adicionar referência ao cliente
                        email_destinatario=dados['email_destinatario'],
                        nome_destinatario=dados['nome_destinatario'],
                        assunto_enviado=email_renderizado['assunto'],
                        corpo_enviado=email_renderizado['corpo_html'],
                        variaveis_utilizadas=dados_serializaveis,
                        status='pendente'
                    )
                    envios_criados += 1
                    
                except Exception as e:
                    self.log("ERROR", "Erro ao criar envio individual", f"Email: {dados.get('email_destinatario', 'N/A')}, Erro: {str(e)}")
            
            self.campanha.total_destinatarios = envios_criados
            self.campanha.save()
            
            self.log("INFO", "Envios individuais criados", f"{envios_criados} envios prontos")
            
        except Exception as e:
            self.log("ERROR", "Erro ao criar envios individuais", str(e))
    
    def _processar_envios(self):
        """Processa os envios de email"""
        try:
            envios = EnvioEmailIndividual.objects.filter(
                campanha=self.campanha,
                status='pendente'
            )
            
            self.log("INFO", "Iniciando envios", f"{envios.count()} emails para enviar")
            
            total_sucessos = 0
            total_erros = 0
            
            for envio in envios:
                try:
                    # Enviar email
                    sucesso, mensagem = self.servico_email.enviar_email(
                        envio.email_destinatario,
                        envio.nome_destinatario,
                        envio.assunto_enviado,
                        envio.corpo_enviado
                    )
                    
                    if sucesso:
                        envio.marcar_enviado()
                        total_sucessos += 1
                        self.log("INFO", "Email enviado", f"{envio.nome_destinatario} <{envio.email_destinatario}>")
                    else:
                        envio.marcar_erro(mensagem)
                        total_erros += 1
                        self.log("ERROR", "Erro no envio", f"{envio.nome_destinatario} <{envio.email_destinatario}>: {mensagem}")
                    
                    # Atualizar estatísticas da campanha
                    self.campanha.total_enviados = total_sucessos + total_erros
                    self.campanha.total_sucessos = total_sucessos
                    self.campanha.total_erros = total_erros
                    self.campanha.save()
                    
                except Exception as e:
                    envio.marcar_erro(str(e))
                    total_erros += 1
                    self.log("ERROR", "Erro no processamento", f"Envio ID {envio.id}: {str(e)}")
            
            self.log("INFO", "Envios processados", f"{total_sucessos} sucessos, {total_erros} erros")
            
        except Exception as e:
            self.log("ERROR", "Erro ao processar envios", str(e))
    
    def _renderizar_template(self, dados_cliente):
        """Renderiza template de email com dados do cliente"""
        try:
            from django.template import Template, Context
            
            # Renderizar assunto
            assunto_template = Template(self.campanha.template_email.assunto)
            assunto = assunto_template.render(Context(dados_cliente))
            
            # Renderizar corpo HTML
            corpo_template = Template(self.campanha.template_email.corpo_html)
            corpo_html = corpo_template.render(Context(dados_cliente))
            
            return {
                'assunto': assunto,
                'corpo_html': corpo_html
            }
            
        except Exception as e:
            self.log("ERROR", "Erro ao renderizar template", str(e))
            return {
                'assunto': self.campanha.template_email.assunto,
                'corpo_html': self.campanha.template_email.corpo_html
            }
    
    def _finalizar_campanha(self):
        """Finaliza a campanha"""
        try:
            self.campanha.data_fim_execucao = timezone.now()
            
            if self.campanha.total_erros == 0:
                self.campanha.atualizar_status('concluida', 'Campanha finalizada com sucesso')
            else:
                self.campanha.atualizar_status('concluida', f'Campanha finalizada com {self.campanha.total_erros} erro(s)')
            
            # Salvar log da execução
            self.campanha.log_execucao = self.log_buffer.getvalue()
            self.campanha.save()
            
            self.log("INFO", "Campanha finalizada", f"Total: {self.campanha.total_enviados}, Sucessos: {self.campanha.total_sucessos}, Erros: {self.campanha.total_erros}")
            
        except Exception as e:
            self.log("ERROR", "Erro ao finalizar campanha", str(e))
    
    def log(self, nivel, acao, mensagem, dados_extras=None):
        """Registra log da execução"""
        timestamp = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        log_line = f"[{timestamp}] {nivel}: {acao} - {mensagem}"
        
        self.log_buffer.write(log_line + "\n")
        
        # Registrar no sistema de logs
        LogEnvioEmail.criar_log(
            nivel.lower(),
            acao.lower().replace(' ', '_'),
            mensagem,
            campanha=self.campanha,
            dados_extras=dados_extras or {}
        )


def executar_campanha_email_background(campanha_id):
    """
    Executa campanha de email em background
    Para usar com threading igual ao sistema existente
    """
    try:
        campanha = CampanhaEmail.objects.get(id=campanha_id)
        executor = ExecutorCampanhaIntegrado(campanha)
        executor.executar_campanha_completa()
        
    except Exception as e:
        logger.error(f"Erro na execução da campanha {campanha_id}: {e}")


def iniciar_campanha_email_async(campanha_id):
    """
    Inicia execução de campanha em thread separada
    Segue o mesmo padrão do sistema existente
    """
    thread = threading.Thread(target=executar_campanha_email_background, args=(campanha_id,))
    thread.daemon = True
    thread.start()
    return thread
