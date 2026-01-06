"""
SERVIÇO SIMPLIFICADO DE EMAILS
Integra com a estrutura existente de ConsultaExecucao
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.template import Template, Context
from django.utils import timezone
from campanhas.models import ConsultaExecucao, ClienteConsultado
from .models import LogEnvioEmail

logger = logging.getLogger(__name__)


class ServicoEmailSimplificado:
    """Serviço simplificado para envio de emails"""
    
    def __init__(self, configuracao_smtp):
        self.config = configuracao_smtp
    
    def enviar_email(self, destinatario_email, destinatario_nome, assunto, corpo_html, corpo_texto=""):
        """Envia um email individual"""
        try:
            # Configurar SMTP
            if self.config.usar_ssl:
                servidor = smtplib.SMTP_SSL(self.config.servidor_smtp, self.config.porta, timeout=30)
            else:
                servidor = smtplib.SMTP(self.config.servidor_smtp, self.config.porta, timeout=30)
                if self.config.usar_tls:
                    servidor.starttls()
            servidor.login(self.config.usuario, self.config.senha)
            
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['Subject'] = assunto
            msg['From'] = f"{self.config.nome_remetente} <{self.config.email_remetente}>"
            msg['To'] = f"{destinatario_nome} <{destinatario_email}>"
            
            # Adicionar conteúdo
            if corpo_texto:
                msg.attach(MIMEText(corpo_texto, 'plain', 'utf-8'))
            if corpo_html:
                msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))
            
            # Enviar
            servidor.send_message(msg)
            servidor.quit()
            
            logger.info(f"Email enviado com sucesso para {destinatario_email}")
            return True, "Enviado com sucesso"
            
        except Exception as e:
            erro = str(e)
            logger.error(f"Erro ao enviar email para {destinatario_email}: {erro}")
            return False, erro


class ExecutorCampanhaSimplificado:
    """Executor simplificado de campanhas"""
    
    def __init__(self, campanha):
        self.campanha = campanha
        self.servico_email = ServicoEmailSimplificado(campanha.configuracao_servidor)
    
    def executar(self):
        """Executa a campanha de forma simplificada"""
        try:
            print(f"🚀 Iniciando campanha: {self.campanha.nome}")
            # Log de início de execução da campanha
            LogEnvioEmail.objects.create(
                campanha=self.campanha,
                nivel='info',
                acao='inicio_execucao',
                mensagem=f'Iniciando execução da campanha {self.campanha.nome}',
                dados_extras={
                    'campanha_id': self.campanha.id,
                    'template_id': getattr(self.campanha.template_email, 'id', None),
                    'config_smtp_id': getattr(self.campanha.configuracao_servidor, 'id', None),
                }
            )
            
            # 1. OBTER DADOS DOS CLIENTES (Método Simplificado)
            clientes_dados = self._obter_dados_clientes()
            
            if not clientes_dados:
                print("❌ Nenhum cliente encontrado com email válido")
                return False
            
            print(f"📊 {len(clientes_dados)} clientes encontrados com email")
            
            # 2. ATUALIZAR CAMPANHA
            self.campanha.status = 'executando'
            self.campanha.total_destinatarios = len(clientes_dados)
            self.campanha.data_inicio_execucao = timezone.now()
            self.campanha.save()
            
            # 3. ENVIAR EMAILS
            sucessos = 0
            erros = 0
            
            for dados_cliente in clientes_dados:
                try:
                    # Renderizar template
                    email_renderizado = self._renderizar_email(dados_cliente)
                    
                    # Enviar email
                    sucesso, mensagem = self.servico_email.enviar_email(
                        dados_cliente['email'],
                        dados_cliente.get('nome_razaosocial', 'Cliente'),
                        email_renderizado['assunto'],
                        email_renderizado['corpo_html'],
                        email_renderizado['corpo_texto']
                    )
                    
                    if sucesso:
                        sucessos += 1
                        print(f"✅ {dados_cliente['nome_razaosocial']} <{dados_cliente['email']}>")
                        # Log de sucesso de envio
                        LogEnvioEmail.objects.create(
                            campanha=self.campanha,
                            nivel='info',
                            acao='envio_sucesso',
                            mensagem='Email enviado com sucesso',
                            dados_extras={
                                'destinatario_email': dados_cliente.get('email'),
                                'destinatario_nome': dados_cliente.get('nome_razaosocial', 'Cliente'),
                            }
                        )
                    else:
                        erros += 1
                        print(f"❌ {dados_cliente['nome_razaosocial']} <{dados_cliente['email']}>: {mensagem}")
                        # Log de erro de envio
                        LogEnvioEmail.objects.create(
                            campanha=self.campanha,
                            nivel='error',
                            acao='envio_erro',
                            mensagem=str(mensagem)[:500],
                            dados_extras={
                                'destinatario_email': dados_cliente.get('email'),
                                'destinatario_nome': dados_cliente.get('nome_razaosocial', 'Cliente'),
                            }
                        )
                    
                    # Registrar envio individual
                    self._registrar_envio_individual(dados_cliente, sucesso, mensagem)
                    
                except Exception as e:
                    erros += 1
                    print(f"❌ Erro ao processar {dados_cliente.get('email', 'N/A')}: {e}")
                    # Log de exceção no processamento individual
                    LogEnvioEmail.objects.create(
                        campanha=self.campanha,
                        nivel='error',
                        acao='processamento_erro',
                        mensagem=str(e)[:500],
                        dados_extras={'destinatario_email': dados_cliente.get('email')}
                    )
            
            # 4. FINALIZAR CAMPANHA
            self.campanha.status = 'concluida'
            self.campanha.total_enviados = sucessos + erros
            self.campanha.total_sucessos = sucessos
            self.campanha.total_erros = erros
            self.campanha.data_fim_execucao = timezone.now()
            self.campanha.save()
            
            print(f"✅ Campanha concluída: {sucessos} sucessos, {erros} erros")
            # Log de fim da execução
            LogEnvioEmail.objects.create(
                campanha=self.campanha,
                nivel='info',
                acao='fim_execucao',
                mensagem='Execução concluída',
                dados_extras={
                    'total_destinatarios': self.campanha.total_destinatarios,
                    'total_sucessos': sucessos,
                    'total_erros': erros,
                }
            )
            return True
            
        except Exception as e:
            self.campanha.status = 'erro'
            self.campanha.save()
            print(f"❌ Erro na execução da campanha: {e}")
            # Log de erro fatal na execução
            LogEnvioEmail.objects.create(
                campanha=self.campanha,
                nivel='critical',
                acao='execucao_erro',
                mensagem=str(e)[:500]
            )
            return False
    
    def _obter_dados_clientes(self):
        """Obtém dados dos clientes usando o método integrado da campanha"""
        try:
            # 🔧 USAR O MÉTODO CORRETO QUE ATUALIZA DADOS E PROCESSA VARIÁVEIS
            print(f"🔧 Chamando obter_clientes_para_envio() para garantir dados atualizados...")
            clientes = self.campanha.obter_clientes_para_envio()
            
            clientes_dados = []
            for cliente in clientes:
                dados = cliente.get_dados_completos()
                email = self._extrair_email(dados)
                
                if email:
                    dados['email'] = email
                    clientes_dados.append(dados)
            
            print(f"📊 {len(clientes_dados)} clientes com email válido encontrados")
            return clientes_dados
            
        except Exception as e:
            print(f"❌ Erro ao obter dados dos clientes: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _extrair_email(self, dados):
        """Extrai email dos dados do cliente"""
        campos_email = ['email', 'email_cliente', 'email_contato', 'e_mail']
        
        for campo in campos_email:
            email = dados.get(campo)
            if email and '@' in str(email):
                return str(email).strip()
        
        return None
    
    def _renderizar_email(self, dados_cliente):
        """Renderiza o template de email com os dados do cliente"""
        try:
            # Renderizar assunto
            assunto_template = Template(self.campanha.template_email.assunto)
            assunto = assunto_template.render(Context(dados_cliente))
            
            # Renderizar corpo HTML
            corpo_template = Template(self.campanha.template_email.corpo_html)
            corpo_html = corpo_template.render(Context(dados_cliente))
            
            # Corpo texto
            corpo_texto = self.campanha.template_email.corpo_texto or ""
            if corpo_texto:
                texto_template = Template(corpo_texto)
                corpo_texto = texto_template.render(Context(dados_cliente))
            
            return {
                'assunto': assunto,
                'corpo_html': corpo_html,
                'corpo_texto': corpo_texto
            }
            
        except Exception as e:
            print(f"❌ Erro ao renderizar template: {e}")
            return {
                'assunto': self.campanha.template_email.assunto,
                'corpo_html': self.campanha.template_email.corpo_html,
                'corpo_texto': self.campanha.template_email.corpo_texto or ""
            }
    
    def _registrar_envio_individual(self, dados_cliente, sucesso, mensagem):
        """Registra o envio individual"""
        try:
            from .models import EnvioEmailIndividual
            from campanhas.models import ClienteConsultado
            
            # Buscar o cliente consultado correspondente
            cliente_consultado = None
            if 'codigo_cliente' in dados_cliente:
                cliente_consultado = ClienteConsultado.objects.filter(
                    codigo_cliente=dados_cliente['codigo_cliente']
                ).first()
            
            # Se não encontrou, criar um registro básico
            if not cliente_consultado:
                cliente_consultado = ClienteConsultado.objects.create(
                    codigo_cliente=dados_cliente.get('codigo_cliente', 'N/A'),
                    nome_razaosocial=dados_cliente.get('nome_razaosocial', 'Cliente'),
                    email=dados_cliente.get('email', ''),
                    consulta_execucao=self.campanha.consulta_execucao
                )
            
            # Usar get_or_create para evitar duplicações
            envio_individual, created = EnvioEmailIndividual.objects.get_or_create(
                campanha=self.campanha,
                cliente=cliente_consultado,
                email_destinatario=dados_cliente['email'],
                defaults={
                    'nome_destinatario': dados_cliente.get('nome_razaosocial', 'Cliente'),
                    'status': 'enviado' if sucesso else 'erro',
                    'data_envio': timezone.now() if sucesso else None,
                    'erro_detalhado': mensagem if not sucesso else ""
                }
            )
            
            # Se já existia, atualizar os dados
            if not created:
                envio_individual.nome_destinatario = dados_cliente.get('nome_razaosocial', 'Cliente')
                envio_individual.status = 'enviado' if sucesso else 'erro'
                envio_individual.data_envio = timezone.now() if sucesso else None
                envio_individual.erro_detalhado = mensagem if not sucesso else ""
                envio_individual.save()
            
        except Exception as e:
            print(f"⚠️ Erro ao registrar envio individual: {e}")
            import traceback
            traceback.print_exc()


def executar_campanha_por_id(campanha_id):
    """Função utilitária para executar campanha por ID"""
    try:
        from .models import CampanhaEmail
        
        campanha = CampanhaEmail.objects.get(id=campanha_id)
        executor = ExecutorCampanhaSimplificado(campanha)
        return executor.executar()
        
    except CampanhaEmail.DoesNotExist:
        print(f"❌ Campanha {campanha_id} não encontrada")
        return False
    except Exception as e:
        print(f"❌ Erro ao executar campanha {campanha_id}: {e}")
        return False
