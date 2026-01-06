import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from django.utils import timezone
from django.db import transaction
from campanhas.models import ClienteConsultado
from .models import (
    CampanhaEmail, EnvioEmailIndividual, LogEnvioEmail,
    ConfiguracaoServidorEmail, TemplateEmail
)
import logging

logger = logging.getLogger(__name__)


class ServicoEnvioEmail:
    """
    Serviço principal para envio de emails
    """
    
    def __init__(self, configuracao_servidor):
        """
        Inicializa o serviço com uma configuração de servidor SMTP
        
        Args:
            configuracao_servidor: instância de ConfiguracaoServidorEmail
        """
        self.configuracao = configuracao_servidor
        self.servidor_smtp = None
    
    def conectar(self):
        """
        Estabelece conexão com o servidor SMTP
        
        Returns:
            bool: True se conectou com sucesso, False caso contrário
        """
        try:
            if self.configuracao.usar_ssl:
                self.servidor_smtp = smtplib.SMTP_SSL(
                    self.configuracao.servidor_smtp,
                    self.configuracao.porta,
                    timeout=self.configuracao.timeout
                )
            else:
                self.servidor_smtp = smtplib.SMTP(
                    self.configuracao.servidor_smtp,
                    self.configuracao.porta,
                    timeout=self.configuracao.timeout
                )
                
                if self.configuracao.usar_tls:
                    self.servidor_smtp.starttls()
            
            # Autenticar
            self.servidor_smtp.login(
                self.configuracao.usuario,
                self.configuracao.senha
            )
            
            logger.info(f"Conectado ao servidor SMTP {self.configuracao.servidor_smtp}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Erro de autenticação SMTP: {str(e)} - Verifique usuário e senha")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"Erro de conexão SMTP: {str(e)} - Verifique servidor e porta")
            return False
        except smtplib.SMTPServerDisconnected as e:
            logger.error(f"Servidor SMTP desconectou: {str(e)} - Conexão perdida inesperadamente")
            return False
        except Exception as e:
            error_msg = str(e)
            if "Connection unexpectedly closed" in error_msg:
                logger.error(f"Conexão SMTP fechada inesperadamente: {error_msg} - Verifique credenciais e configurações de segurança")
            elif "Authentication failed" in error_msg:
                logger.error(f"Falha na autenticação SMTP: {error_msg} - Senha incorreta ou conta bloqueada")
            else:
                logger.error(f"Erro desconhecido ao conectar SMTP: {error_msg}")
            return False
    
    def desconectar(self):
        """Fecha a conexão com o servidor SMTP"""
        if self.servidor_smtp:
            try:
                self.servidor_smtp.quit()
            except:
                pass
            self.servidor_smtp = None
    
    def enviar_email_individual(self, destinatario_email, destinatario_nome, assunto, corpo_html, corpo_texto=None, anexos=None):
        """
        Envia um email individual
        
        Args:
            destinatario_email: email do destinatário
            destinatario_nome: nome do destinatário
            assunto: assunto do email
            corpo_html: corpo do email em HTML
            corpo_texto: corpo do email em texto puro (opcional)
            anexos: lista de caminhos de arquivos para anexar (opcional)
        
        Returns:
            tuple: (sucesso: bool, message_id: str, erro: str, tempo_ms: int)
        """
        inicio = time.time()
        
        try:
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['Subject'] = assunto
            msg['From'] = f"{self.configuracao.nome_remetente} <{self.configuracao.email_remetente}>" if self.configuracao.nome_remetente else self.configuracao.email_remetente
            msg['To'] = f"{destinatario_nome} <{destinatario_email}>" if destinatario_nome else destinatario_email
            
            # Adicionar corpo em texto puro se fornecido
            if corpo_texto:
                texto_part = MIMEText(corpo_texto, 'plain', 'utf-8')
                msg.attach(texto_part)
            
            # Adicionar corpo HTML
            html_part = MIMEText(corpo_html, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Adicionar anexos se fornecidos
            if anexos:
                for anexo in anexos:
                    try:
                        with open(anexo, 'rb') as f:
                            anexo_part = MIMEBase('application', 'octet-stream')
                            anexo_part.set_payload(f.read())
                            encoders.encode_base64(anexo_part)
                            anexo_part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {anexo.split("/")[-1]}'
                            )
                            msg.attach(anexo_part)
                    except Exception as e:
                        logger.warning(f"Erro ao anexar arquivo {anexo}: {str(e)}")
            
            # Enviar email
            resposta = self.servidor_smtp.send_message(msg)
            
            # Calcular tempo de envio
            tempo_ms = int((time.time() - inicio) * 1000)
            
            # Extrair message ID se disponível
            message_id = msg.get('Message-ID', '')
            
            logger.info(f"Email enviado com sucesso para {destinatario_email}")
            return True, message_id, None, tempo_ms
            
        except Exception as e:
            tempo_ms = int((time.time() - inicio) * 1000)
            erro = str(e)
            logger.error(f"Erro ao enviar email para {destinatario_email}: {erro}")
            return False, None, erro, tempo_ms
    
    def __enter__(self):
        """Context manager - entrada"""
        self.conectar()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager - saída"""
        self.desconectar()


class GerenciadorCampanhaEmail:
    """
    Gerenciador para executar campanhas de email
    """
    
    def __init__(self, campanha):
        """
        Inicializa o gerenciador com uma campanha
        
        Args:
            campanha: instância de CampanhaEmail
        """
        self.campanha = campanha
        self.servico_email = None
    
    def preparar_dados_clientes(self):
        """
        Prepara os dados dos clientes para envio baseado na configuração da campanha
        
        Returns:
            list: lista de dados dos clientes
        """
        clientes_dados = []
        
        try:
            if self.campanha.consulta_execucao:
                # Usar dados de uma execução específica
                from campanhas.models import ConsultaCliente
                consultas_clientes = ConsultaCliente.objects.filter(execucao=self.campanha.consulta_execucao)
                clientes = ClienteConsultado.objects.filter(
                    consultacliente__in=consultas_clientes
                ).distinct()
                
                for cliente in clientes:
                    dados = cliente.get_dados_completos()
                    
                    # Verificar se o cliente tem email
                    email = self._extrair_email_cliente(dados)
                    if email:
                        dados['email_destinatario'] = email
                        dados['nome_destinatario'] = dados.get('nome_razaosocial', 'Cliente')
                        clientes_dados.append(dados)
            
            elif self.campanha.template_sql:
                # Executar consulta SQL para obter dados
                from django.db import connection
                
                with connection.cursor() as cursor:
                    cursor.execute(self.campanha.template_sql.consulta_sql)
                    resultados = cursor.fetchall()
                    colunas = [desc[0] for desc in cursor.description]
                    
                    for linha in resultados:
                        dados = dict(zip(colunas, linha))
                        
                        # Verificar se tem email
                        email = self._extrair_email_cliente(dados)
                        if email:
                            dados['email_destinatario'] = email
                            dados['nome_destinatario'] = dados.get('nome_razaosocial', 'Cliente')
                            clientes_dados.append(dados)
                        else:
                            logger.warning(f"Cliente sem email válido: {dados}")
                            
                logger.info(f"Template SQL executado: {len(clientes_dados)} clientes com email válido")
            
            self.campanha.total_destinatarios = len(clientes_dados)
            self.campanha.save(update_fields=['total_destinatarios'])
            
            LogEnvioEmail.criar_log(
                'info', 'preparar_dados',
                f"Preparados dados de {len(clientes_dados)} clientes para envio",
                campanha=self.campanha
            )
            
            return clientes_dados
            
        except Exception as e:
            erro = f"Erro ao preparar dados dos clientes: {str(e)}"
            logger.error(erro)
            LogEnvioEmail.criar_log('error', 'preparar_dados', erro, campanha=self.campanha)
            return []
    
    def _extrair_email_cliente(self, dados_cliente):
        """
        Extrai o email do cliente dos dados disponíveis
        
        Args:
            dados_cliente: dicionário com dados do cliente
        
        Returns:
            str: email do cliente ou None se não encontrado
        """
        # Campos possíveis onde o email pode estar
        campos_email = ['email', 'email_cliente', 'email_contato', 'e_mail']
        
        for campo in campos_email:
            email = dados_cliente.get(campo)
            if email and '@' in str(email):
                return str(email).strip()
        
        # Verificar em dados dinâmicos
        dados_dinamicos = dados_cliente.get('dados_dinamicos', {})
        if isinstance(dados_dinamicos, dict):
            for campo in campos_email:
                email = dados_dinamicos.get(campo)
                if email and '@' in str(email):
                    return str(email).strip()
        
        return None
    
    def criar_envios_individuais(self, dados_clientes):
        """
        Cria registros de envios individuais para cada cliente
        
        Args:
            dados_clientes: lista de dados dos clientes
        
        Returns:
            int: número de envios criados
        """
        envios_criados = 0
        
        try:
            with transaction.atomic():
                for dados in dados_clientes:
                    # Verificar se já existe envio para este cliente
                    cliente_obj = None
                    if 'codigo_cliente' in dados:
                        try:
                            cliente_obj = ClienteConsultado.objects.get(
                                codigo_cliente=dados['codigo_cliente']
                            )
                        except ClienteConsultado.DoesNotExist:
                            logger.warning(f"Cliente {dados['codigo_cliente']} não encontrado")
                            continue
                    
                    email = dados.get('email_destinatario')
                    nome = dados.get('nome_destinatario', 'Cliente')
                    
                    if not email or not cliente_obj:
                        continue
                    
                    # Renderizar template
                    template_renderizado = self.campanha.template_email.renderizar_template(dados)
                    
                    # Criar ou atualizar envio individual
                    envio, criado = EnvioEmailIndividual.objects.get_or_create(
                        campanha=self.campanha,
                        cliente=cliente_obj,
                        email_destinatario=email,
                        defaults={
                            'nome_destinatario': nome,
                            'status': 'pendente',
                            'assunto_enviado': template_renderizado['assunto'],
                            'corpo_enviado': template_renderizado['corpo_html'],
                            'variaveis_utilizadas': dados,
                            'data_agendamento': timezone.now()
                        }
                    )
                    
                    if criado:
                        envios_criados += 1
            
            self.campanha.total_pendentes = envios_criados
            self.campanha.save(update_fields=['total_pendentes'])
            
            LogEnvioEmail.criar_log(
                'info', 'criar_envios',
                f"Criados {envios_criados} envios individuais",
                campanha=self.campanha
            )
            
            return envios_criados
            
        except Exception as e:
            erro = f"Erro ao criar envios individuais: {str(e)}"
            logger.error(erro)
            LogEnvioEmail.criar_log('error', 'criar_envios', erro, campanha=self.campanha)
            return 0
    
    def executar_envios(self):
        """
        Executa os envios de email da campanha
        
        Returns:
            bool: True se executou com sucesso, False caso contrário
        """
        try:
            # Verificar se pode executar
            if not self.campanha.pode_executar():
                logger.warning(f"Campanha {self.campanha.nome} não pode ser executada")
                return False
            
            # Atualizar status para executando
            self.campanha.atualizar_status('executando', 'Iniciando execução da campanha')
            
            # Preparar dados dos clientes
            dados_clientes = self.preparar_dados_clientes()
            if not dados_clientes:
                self.campanha.atualizar_status('erro', 'Nenhum cliente encontrado para envio')
                return False
            
            # Criar envios individuais
            envios_criados = self.criar_envios_individuais(dados_clientes)
            if envios_criados == 0:
                self.campanha.atualizar_status('erro', 'Nenhum envio individual foi criado')
                return False
            
            # Inicializar serviço de email
            self.servico_email = ServicoEnvioEmail(self.campanha.configuracao_servidor)
            
            with self.servico_email:
                # Obter envios pendentes
                envios_pendentes = EnvioEmailIndividual.objects.filter(
                    campanha=self.campanha,
                    status='pendente'
                ).order_by('data_agendamento')
                
                # Aplicar limite se configurado
                if self.campanha.limite_envios_por_execucao > 0:
                    envios_pendentes = envios_pendentes[:self.campanha.limite_envios_por_execucao]
                
                envios_processados = 0
                
                for envio in envios_pendentes:
                    try:
                        # Marcar como enviando
                        envio.status = 'enviando'
                        envio.save(update_fields=['status'])
                        
                        # Enviar email
                        sucesso, message_id, erro, tempo_ms = self.servico_email.enviar_email_individual(
                            envio.email_destinatario,
                            envio.nome_destinatario,
                            envio.assunto_enviado,
                            envio.corpo_enviado,
                            anexos=envio.anexos_enviados
                        )
                        
                        if sucesso:
                            envio.marcar_enviado(message_id, None, tempo_ms)
                            LogEnvioEmail.criar_log(
                                'info', 'envio_sucesso',
                                f"Email enviado com sucesso para {envio.email_destinatario}",
                                campanha=self.campanha,
                                envio_individual=envio
                            )
                        else:
                            envio.marcar_erro(erro, None, tempo_ms)
                            LogEnvioEmail.criar_log(
                                'error', 'envio_erro',
                                f"Erro ao enviar email para {envio.email_destinatario}: {erro}",
                                campanha=self.campanha,
                                envio_individual=envio
                            )
                        
                        envios_processados += 1
                        
                        # Aplicar intervalo entre envios se configurado
                        if self.campanha.intervalo_entre_envios > 0:
                            time.sleep(self.campanha.intervalo_entre_envios)
                        
                    except Exception as e:
                        erro = f"Erro ao processar envio para {envio.email_destinatario}: {str(e)}"
                        logger.error(erro)
                        envio.marcar_erro(erro)
                        LogEnvioEmail.criar_log(
                            'error', 'envio_erro',
                            erro,
                            campanha=self.campanha,
                            envio_individual=envio
                        )
                
                # Verificar se há mais envios pendentes
                envios_restantes = EnvioEmailIndividual.objects.filter(
                    campanha=self.campanha,
                    status='pendente'
                ).count()
                
                if envios_restantes == 0:
                    # Campanha concluída
                    self.campanha.atualizar_status(
                        'concluida',
                        f'Campanha concluída. Processados {envios_processados} envios.'
                    )
                else:
                    # Ainda há envios pendentes
                    if self.campanha.tipo_agendamento == 'unico':
                        self.campanha.atualizar_status(
                            'pausada',
                            f'Processados {envios_processados} envios. {envios_restantes} ainda pendentes.'
                        )
                    else:
                        # Agendar próxima execução
                        self.campanha.atualizar_status(
                            'agendada',
                            f'Processados {envios_processados} envios. Agendada próxima execução.'
                        )
                
                return True
                
        except Exception as e:
            erro = f"Erro durante execução da campanha: {str(e)}"
            logger.error(erro)
            self.campanha.atualizar_status('erro', erro)
            LogEnvioEmail.criar_log('critical', 'execucao_erro', erro, campanha=self.campanha)
            return False
    
    @classmethod
    def executar_campanhas_agendadas(cls):
        """
        Executa todas as campanhas que estão agendadas para execução
        
        Returns:
            int: número de campanhas executadas
        """
        agora = timezone.now()
        
        campanhas_agendadas = CampanhaEmail.objects.filter(
            status='agendada',
            ativo=True,
            data_agendamento__lte=agora
        )
        
        executadas = 0
        
        for campanha in campanhas_agendadas:
            if campanha.pode_executar():
                gerenciador = cls(campanha)
                if gerenciador.executar_envios():
                    executadas += 1
        
        return executadas


def testar_configuracao_smtp(configuracao_id):
    """
    Testa uma configuração SMTP
    
    Args:
        configuracao_id: ID da configuração a ser testada
    
    Returns:
        tuple: (sucesso: bool, mensagem: str)
    """
    try:
        configuracao = ConfiguracaoServidorEmail.objects.get(id=configuracao_id)
        return configuracao.testar_conexao()
    except ConfiguracaoServidorEmail.DoesNotExist:
        return False, "Configuração não encontrada"
    except Exception as e:
        return False, f"Erro ao testar configuração: {str(e)}"


def obter_estatisticas_campanha(campanha_id):
    """
    Obtém estatísticas detalhadas de uma campanha
    
    Args:
        campanha_id: ID da campanha
    
    Returns:
        dict: estatísticas da campanha
    """
    try:
        campanha = CampanhaEmail.objects.get(id=campanha_id)
        
        envios = EnvioEmailIndividual.objects.filter(campanha=campanha)
        
        stats = {
            'total_destinatarios': campanha.total_destinatarios,
            'total_enviados': campanha.total_enviados,
            'total_sucessos': campanha.total_sucessos,
            'total_erros': campanha.total_erros,
            'total_pendentes': campanha.total_pendentes,
            'taxa_sucesso': campanha.get_taxa_sucesso(),
            'progresso': campanha.get_progresso_percentual(),
            'status': campanha.get_status_display(),
            'data_inicio': campanha.data_inicio_execucao,
            'data_fim': campanha.data_fim_execucao,
            'proxima_execucao': campanha.proxima_execucao,
            'detalhes_por_status': {}
        }
        
        # Contar por status
        for status, _ in EnvioEmailIndividual.STATUS_CHOICES:
            count = envios.filter(status=status).count()
            stats['detalhes_por_status'][status] = count
        
        return stats
        
    except CampanhaEmail.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas da campanha {campanha_id}: {str(e)}")
        return None
