"""
Comando para executar campanhas de email agendadas e recorrentes.

Este comando deve ser executado periodicamente (ex: a cada minuto via cron)
para verificar e executar campanhas que estão prontas para execução.

Uso:
    python manage.py executar_campanhas_agendadas
    
Cron example (executar a cada minuto):
    * * * * * cd /path/to/project && python manage.py executar_campanhas_agendadas
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from emails.models import CampanhaEmail, LogEnvioEmail
from emails.executor_integrado import ExecutorCampanhaIntegrado, iniciar_campanha_email_async
import logging
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executa campanhas de email agendadas e recorrentes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra quais campanhas seriam executadas, sem executar de fato',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostra informações detalhadas durante a execução',
        )
        parser.add_argument(
            '--max-campanhas',
            type=int,
            default=50,
            help='Número máximo de campanhas a processar por execução (padrão: 50)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        max_campanhas = options['max_campanhas']
        
        agora = timezone.now()
        
        if verbose:
            self.stdout.write(
                self.style.SUCCESS(f'🚀 Iniciando verificação de campanhas agendadas - {agora.strftime("%d/%m/%Y %H:%M:%S")}')
            )
        
        # Buscar campanhas que devem ser executadas
        campanhas_para_executar = self.buscar_campanhas_para_execucao(agora, max_campanhas)
        
        if not campanhas_para_executar:
            if verbose:
                self.stdout.write('ℹ️  Nenhuma campanha para executar no momento')
            return
        
        if verbose or dry_run:
            self.stdout.write(
                self.style.WARNING(f'📋 Encontradas {len(campanhas_para_executar)} campanha(s) para executar:')
            )
        
        campanhas_executadas = 0
        campanhas_com_erro = 0
        
        for campanha in campanhas_para_executar:
            try:
                if verbose or dry_run:
                    self.mostrar_info_campanha(campanha)
                
                if not dry_run:
                    sucesso = self.executar_campanha(campanha, verbose)
                    if sucesso:
                        campanhas_executadas += 1
                    else:
                        campanhas_com_erro += 1
                else:
                    campanhas_executadas += 1
                    
            except Exception as e:
                campanhas_com_erro += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ Erro ao processar campanha {campanha.id} ({campanha.nome}): {str(e)}')
                )
                logger.error(f'Erro ao executar campanha {campanha.id}: {str(e)}', exc_info=True)
        
        # Resumo final
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'✅ DRY RUN: {campanhas_executadas} campanha(s) seriam executadas')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Execução concluída: {campanhas_executadas} executada(s), '
                    f'{campanhas_com_erro} com erro'
                )
            )
    
    def buscar_campanhas_para_execucao(self, agora, limite):
        """
        Busca campanhas que devem ser executadas agora
        """
        campanhas = CampanhaEmail.objects.filter(
            ativo=True,
            ativa_recorrencia=True,
            proxima_execucao__isnull=False,
            proxima_execucao__lte=agora + timedelta(minutes=1),  # Margem de 1 minuto
            status__in=['agendada', 'rascunho']
        ).select_related(
            'template_email',
            'template_sql',
            'configuracao_servidor',
            'consulta_execucao'
        )[:limite]
        
        # Filtrar campanhas que realmente devem executar
        campanhas_validas = []
        for campanha in campanhas:
            if campanha.deve_executar_agora():
                # Verificar se não passou do fim da recorrência
                if campanha.data_fim_recorrencia and agora > campanha.data_fim_recorrencia:
                    # Desativar campanha que passou do prazo
                    campanha.ativa_recorrencia = False
                    campanha.status = 'concluida'
                    campanha.save(update_fields=['ativa_recorrencia', 'status'])
                    continue
                
                campanhas_validas.append(campanha)
        
        return campanhas_validas
    
    def mostrar_info_campanha(self, campanha):
        """
        Mostra informações da campanha
        """
        tipo_fonte = "SQL" if campanha.template_sql else "Execução"
        self.stdout.write(f'  📧 {campanha.nome}')
        self.stdout.write(f'     ID: {campanha.id}')
        self.stdout.write(f'     Tipo: {campanha.get_tipo_agendamento_display()}')
        self.stdout.write(f'     Fonte: {tipo_fonte}')
        self.stdout.write(f'     Próxima execução: {campanha.proxima_execucao.strftime("%d/%m/%Y %H:%M")}')
        
        if campanha.data_fim_recorrencia:
            self.stdout.write(f'     Fim da recorrência: {campanha.data_fim_recorrencia.strftime("%d/%m/%Y %H:%M")}')
    
    def executar_campanha(self, campanha, verbose=False):
        """
        Executa uma campanha específica
        """
        try:
            if verbose:
                self.stdout.write(f'🔄 Executando campanha: {campanha.nome}')
            
            # Log de início
            LogEnvioEmail.criar_log(
                nivel='info',
                acao='execucao_agendada_iniciada',
                mensagem=f'Execução automática iniciada para campanha: {campanha.nome}',
                campanha=campanha,
                dados_extras={
                    'tipo_agendamento': campanha.tipo_agendamento,
                    'proxima_execucao': campanha.proxima_execucao.isoformat() if campanha.proxima_execucao else None
                }
            )
            
            # Atualizar status da campanha
            campanha.status = 'executando'
            campanha.save(update_fields=['status'])
            
            # REPROCESSAR DADOS ANTES DO ENVIO (ESSENCIAL PARA RECORRÊNCIA)
            if verbose:
                self.stdout.write('  🔄 Reprocessando dados dos clientes...')
            
            executor = ExecutorCampanhaIntegrado(campanha)
            
            # Sempre criar nova execução para campanhas recorrentes
            if campanha.tipo_agendamento != 'unico':
                # Forçar criação de nova execução
                campanha.consulta_execucao = None
                campanha.save(update_fields=['consulta_execucao'])
            
            # Obter dados atualizados
            dados_clientes = executor._obter_dados_clientes_integrado()
            
            if not dados_clientes:
                if verbose:
                    self.stdout.write('  ⚠️  Nenhum cliente encontrado para envio')
                
                LogEnvioEmail.criar_log(
                    nivel='warning',
                    acao='nenhum_cliente_encontrado',
                    mensagem='Nenhum cliente encontrado para envio na execução agendada',
                    campanha=campanha
                )
                
                # Marcar como concluída e calcular próxima execução
                campanha.marcar_execucao_concluida()
                return True
            
            if verbose:
                self.stdout.write(f'  📊 {len(dados_clientes)} cliente(s) encontrado(s)')
            
            # Atualizar total de destinatários
            campanha.total_destinatarios = len(dados_clientes)
            campanha.save(update_fields=['total_destinatarios'])
            
            # Executar envios em background
            def executar_envios():
                try:
                    iniciar_campanha_email_async(campanha.id)
                    
                    # Marcar execução como concluída e calcular próxima
                    campanha.marcar_execucao_concluida()
                    
                    LogEnvioEmail.criar_log(
                        nivel='info',
                        acao='execucao_agendada_concluida',
                        mensagem=f'Execução automática concluída para campanha: {campanha.nome}',
                        campanha=campanha,
                        dados_extras={
                            'total_enviados': campanha.total_enviados,
                            'total_erros': campanha.total_erros,
                            'proxima_execucao': campanha.proxima_execucao.isoformat() if campanha.proxima_execucao else None
                        }
                    )
                    
                except Exception as e:
                    logger.error(f'Erro na execução da campanha {campanha.id}: {str(e)}', exc_info=True)
                    
                    campanha.status = 'erro'
                    campanha.save(update_fields=['status'])
                    
                    LogEnvioEmail.criar_log(
                        nivel='error',
                        acao='erro_execucao_agendada',
                        mensagem=f'Erro na execução automática: {str(e)}',
                        campanha=campanha,
                        dados_extras={'erro': str(e)}
                    )
            
            # Iniciar thread para execução dos envios
            thread = threading.Thread(target=executar_envios)
            thread.daemon = True
            thread.start()
            
            if verbose:
                self.stdout.write(f'  ✅ Campanha iniciada em background')
            
            return True
            
        except Exception as e:
            logger.error(f'Erro ao executar campanha {campanha.id}: {str(e)}', exc_info=True)
            
            # Marcar campanha com erro
            campanha.status = 'erro'
            campanha.save(update_fields=['status'])
            
            LogEnvioEmail.criar_log(
                nivel='error',
                acao='erro_execucao_agendada',
                mensagem=f'Erro crítico na execução automática: {str(e)}',
                campanha=campanha,
                dados_extras={'erro': str(e)}
            )
            
            return False
