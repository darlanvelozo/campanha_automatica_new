#!/usr/bin/env python3
"""
Comando Django para executar o monitor de campanhas como daemon.
Este comando é otimizado para funcionar com systemd.
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from emails.models import CampanhaEmail
from emails.servico_simplificado import ExecutorCampanhaSimplificado

# Configurar logging simples
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executa o monitor de campanhas como daemon para systemd'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True
        self.check_interval = 30  # Verificar a cada 30 segundos
        
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Intervalo em segundos entre verificações (padrão: 30)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostra informações detalhadas durante a execução',
        )
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Executa como daemon (para systemd)',
        )
    
    def handle(self, *args, **options):
        self.check_interval = options['interval']
        verbose = options['verbose']
        daemon_mode = options['daemon']
        
        # Configurar handler para SIGTERM e SIGINT
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        logger.info(f"🚀 Iniciando monitor de campanhas (intervalo: {self.check_interval}s)")
        if daemon_mode:
            logger.info("🔧 Modo daemon ativado")
        
        try:
            while self.running:
                self.verificar_campanhas(verbose)
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("⏹️  Monitor interrompido pelo usuário")
        except Exception as e:
            logger.error(f"❌ Erro no monitor: {str(e)}", exc_info=True)
        finally:
            logger.info("🛑 Monitor de campanhas finalizado")
    
    def signal_handler(self, signum, frame):
        """Handler para sinais de interrupção"""
        logger.info(f"📡 Sinal {signum} recebido, finalizando monitor...")
        self.running = False
    
    def verificar_campanhas(self, verbose=False):
        """Verifica e executa campanhas que devem ser executadas agora"""
        agora = timezone.now()
        agora_brasilia = timezone.localtime(agora)
        
        if verbose:
            logger.info(f"🔍 Verificando campanhas - {agora_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
        
        # Inicializar campanhas que não têm próxima execução
        self.inicializar_campanhas_sem_execucao()
        
        # Mostrar resumo das campanhas ativas
        if verbose:
            self.mostrar_resumo_campanhas_ativas()
        else:
            self.mostrar_resumo_compacto()
        
        # Buscar campanhas que devem ser executadas
        campanhas_para_executar = self.buscar_campanhas_para_execucao(agora)
        
        if not campanhas_para_executar:
            if verbose:
                logger.info("ℹ️  Nenhuma campanha para executar no momento")
            return
        
        logger.info(f"📋 Encontradas {len(campanhas_para_executar)} campanha(s) para executar")
        
        campanhas_executadas = 0
        campanhas_com_erro = 0
        
        for campanha in campanhas_para_executar:
            try:
                if verbose:
                    self.mostrar_info_campanha(campanha)
                
                sucesso = self.executar_campanha(campanha, verbose)
                if sucesso:
                    campanhas_executadas += 1
                else:
                    campanhas_com_erro += 1
                    
            except Exception as e:
                campanhas_com_erro += 1
                logger.error(f"❌ Erro ao processar campanha {campanha.id} ({campanha.nome}): {str(e)}")
        
        # Resumo
        logger.info(f"✅ Execução concluída: {campanhas_executadas} executada(s), {campanhas_com_erro} com erro")
        
        # Mostrar próximo ciclo
        if verbose:
            proxima_verificacao = agora + timedelta(seconds=self.intervalo)
            proxima_brasilia = timezone.localtime(proxima_verificacao)
            logger.info(f"🔄 Próxima verificação: {proxima_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
    
    def mostrar_resumo_campanhas_ativas(self):
        """Mostra resumo de todas as campanhas ativas e suas previsões"""
        agora = timezone.now()
        agora_brasilia = timezone.localtime(agora)
        
        # Buscar todas as campanhas ativas
        campanhas_ativas = CampanhaEmail.objects.filter(
            ativo=True,
            status__in=['agendada', 'executando', 'pausada']
        ).select_related(
            'template_email',
            'template_sql',
            'configuracao_servidor'
        ).order_by('proxima_execucao', 'data_agendamento')
        
        if not campanhas_ativas.exists():
            logger.info("📋 Nenhuma campanha ativa encontrada")
            return
        
        logger.info(f"📋 RESUMO DAS CAMPANHAS ATIVAS ({campanhas_ativas.count()} total)")
        logger.info("=" * 80)
        
        # Contadores por tipo
        contadores = {
            'unico': 0,
            'diario': 0,
            'semanal': 0,
            'mensal': 0,
            'personalizado': 0,
            'executando': 0,
            'pausada': 0
        }
        
        for campanha in campanhas_ativas:
            # Contar por tipo
            if campanha.status == 'executando':
                contadores['executando'] += 1
            elif campanha.status == 'pausada':
                contadores['pausada'] += 1
            else:
                contadores[campanha.tipo_agendamento] += 1
            
            # Determinar próxima execução
            proxima_execucao = None
            if campanha.tipo_agendamento == 'unico':
                proxima_execucao = campanha.data_agendamento
            else:
                proxima_execucao = campanha.proxima_execucao
            
            # Status visual
            if campanha.status == 'executando':
                status_icon = "🔄"
                status_text = "EXECUTANDO"
            elif campanha.status == 'pausada':
                status_icon = "⏸️"
                status_text = "PAUSADA"
            else:
                status_icon = "⏰"
                status_text = "AGENDADA"
            
            # Tipo de agendamento
            tipo_display = {
                'unico': 'Único',
                'diario': 'Diário',
                'semanal': 'Semanal',
                'mensal': 'Mensal',
                'personalizado': 'Cron'
            }.get(campanha.tipo_agendamento, campanha.tipo_agendamento)
            
            # Informações da campanha
            logger.info(f"{status_icon} {campanha.nome}")
            logger.info(f"   📊 ID: {campanha.id} | Tipo: {tipo_display} | Status: {status_text}")
            
            if proxima_execucao:
                proxima_brasilia = timezone.localtime(proxima_execucao)
                tempo_restante = proxima_execucao - agora
                
                if tempo_restante.total_seconds() > 0:
                    if tempo_restante.days > 0:
                        tempo_texto = f"{tempo_restante.days}d {tempo_restante.seconds//3600}h {(tempo_restante.seconds//60)%60}m"
                    elif tempo_restante.seconds > 3600:
                        tempo_texto = f"{tempo_restante.seconds//3600}h {(tempo_restante.seconds//60)%60}m"
                    elif tempo_restante.seconds > 60:
                        tempo_texto = f"{tempo_restante.seconds//60}m {tempo_restante.seconds%60}s"
                    else:
                        tempo_texto = f"{tempo_restante.seconds}s"
                    
                    logger.info(f"   ⏰ Próxima execução: {proxima_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
                    logger.info(f"   ⏳ Tempo restante: {tempo_texto}")
                else:
                    logger.info(f"   ⚡ Próxima execução: {proxima_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília) - DEVIA EXECUTAR AGORA!")
            else:
                logger.info(f"   ❌ Próxima execução: Não definida")
            
            # Estatísticas
            if campanha.total_enviados > 0:
                taxa_sucesso = (campanha.total_sucessos / campanha.total_enviados) * 100
                logger.info(f"   📈 Estatísticas: {campanha.total_enviados} enviados | {campanha.total_sucessos} sucessos | {taxa_sucesso:.1f}% taxa")
            
            logger.info("")
        
        # Resumo por tipo
        logger.info("📊 RESUMO POR TIPO:")
        logger.info(f"   🔄 Executando: {contadores['executando']}")
        logger.info(f"   ⏸️ Pausadas: {contadores['pausada']}")
        logger.info(f"   📅 Únicas: {contadores['unico']}")
        logger.info(f"   📆 Diárias: {contadores['diario']}")
        logger.info(f"   📅 Semanais: {contadores['semanal']}")
        logger.info(f"   📆 Mensais: {contadores['mensal']}")
        logger.info(f"   ⚙️ Cron: {contadores['personalizado']}")
        logger.info("=" * 80)
    
    def mostrar_resumo_compacto(self):
        """Mostra resumo compacto das campanhas ativas"""
        agora = timezone.now()
        
        # Contar campanhas ativas
        total_ativas = CampanhaEmail.objects.filter(ativo=True).count()
        executando = CampanhaEmail.objects.filter(ativo=True, status='executando').count()
        agendadas = CampanhaEmail.objects.filter(ativo=True, status='agendada').count()
        pausadas = CampanhaEmail.objects.filter(ativo=True, status='pausada').count()
        
        # Próximas execuções (próximas 3)
        proximas_execucoes = CampanhaEmail.objects.filter(
            ativo=True,
            status='agendada',
            proxima_execucao__isnull=False
        ).order_by('proxima_execucao')[:3]
        
        logger.info(f"📊 Campanhas: {total_ativas} ativas | {executando} executando | {agendadas} agendadas | {pausadas} pausadas")
        
        if proximas_execucoes.exists():
            logger.info("⏰ Próximas execuções:")
            for campanha in proximas_execucoes:
                proxima_brasilia = timezone.localtime(campanha.proxima_execucao)
                tempo_restante = campanha.proxima_execucao - agora
                
                if tempo_restante.total_seconds() > 0:
                    if tempo_restante.days > 0:
                        tempo_texto = f"{tempo_restante.days}d {tempo_restante.seconds//3600}h"
                    elif tempo_restante.seconds > 3600:
                        tempo_texto = f"{tempo_restante.seconds//3600}h {(tempo_restante.seconds//60)%60}m"
                    elif tempo_restante.seconds > 60:
                        tempo_texto = f"{tempo_restante.seconds//60}m"
                    else:
                        tempo_texto = f"{tempo_restante.seconds}s"
                    
                    logger.info(f"   • {campanha.nome}: {proxima_brasilia.strftime('%d/%m %H:%M')} (em {tempo_texto})")
                else:
                    logger.info(f"   • {campanha.nome}: {proxima_brasilia.strftime('%d/%m %H:%M')} (AGORA!)")
    
    def inicializar_campanhas_sem_execucao(self):
        """
        Inicializa campanhas que não têm próxima execução definida
        
        IMPORTANTE: Este método APENAS calcula e define a próxima execução.
        NÃO executa consultas SQL/API nem envia emails.
        Os dados serão atualizados apenas quando a campanha for realmente executada.
        """
        campanhas_sem_execucao = CampanhaEmail.objects.filter(
            ativo=True,
            ativa_recorrencia=True,
            proxima_execucao__isnull=True,
            status__in=['agendada', 'rascunho']
        )
        
        for campanha in campanhas_sem_execucao:
            try:
                proxima_execucao = campanha.calcular_proxima_execucao()
                if proxima_execucao:
                    campanha.proxima_execucao = proxima_execucao
                    campanha.save(update_fields=['proxima_execucao'])
                    proxima_brasilia = timezone.localtime(proxima_execucao)
                    logger.info(f"📅 Campanha {campanha.nome} inicializada - próxima execução: {proxima_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
                else:
                    logger.warning(f"⚠️ Não foi possível calcular próxima execução para campanha {campanha.nome}")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar campanha {campanha.nome}: {str(e)}")
    
    def buscar_campanhas_para_execucao(self, agora):
        """Busca campanhas que devem ser executadas agora"""
        campanhas = CampanhaEmail.objects.filter(
            ativo=True,
            status__in=['agendada', 'rascunho', 'erro']
        ).select_related(
            'template_email',
            'template_sql',
            'configuracao_servidor',
            'consulta_execucao'
        )
        
        campanhas_validas = []
        
        for campanha in campanhas:
            deve_executar = False
            
            # Verificar tipo de agendamento
            if campanha.tipo_agendamento == 'unico':
                # Envio único - verificar se chegou a hora
                if campanha.data_agendamento and campanha.data_agendamento <= agora + timedelta(minutes=1):
                    deve_executar = True
                    data_brasilia = timezone.localtime(campanha.data_agendamento)
                    logger.info(f"📅 Envio único agendado para: {data_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
                    
            elif campanha.tipo_agendamento in ['diario', 'semanal', 'mensal', 'personalizado']:
                # Campanhas recorrentes - verificar se deve executar agora
                if campanha.ativa_recorrencia:
                    if campanha.deve_executar_agora():
                        deve_executar = True
                        proxima_brasilia = timezone.localtime(campanha.proxima_execucao)
                        logger.info(f"🔄 Campanha recorrente ({campanha.get_tipo_agendamento_display()}) - próxima execução: {proxima_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
                    else:
                        # Log para debug - mostrar quando será a próxima execução
                        if campanha.proxima_execucao:
                            proxima_brasilia = timezone.localtime(campanha.proxima_execucao)
                            logger.debug(f"⏳ Campanha {campanha.nome} - próxima execução: {proxima_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
            
            if deve_executar:
                # Verificar se não passou do fim da recorrência
                if campanha.data_fim_recorrencia and agora > campanha.data_fim_recorrencia:
                    # Desativar campanha que passou do prazo
                    campanha.ativa_recorrencia = False
                    campanha.status = 'concluida'
                    campanha.save(update_fields=['ativa_recorrencia', 'status'])
                    fim_brasilia = timezone.localtime(campanha.data_fim_recorrencia)
                    logger.info(f"⏰ Campanha {campanha.nome} finalizada (passou do prazo: {fim_brasilia.strftime('%d/%m/%Y %H:%M:%S')} Brasília)")
                    continue
                
                # Verificar se a campanha pode executar (dados válidos, etc.)
                if campanha.pode_executar():
                    campanhas_validas.append(campanha)
                else:
                    logger.warning(f"⚠️ Campanha {campanha.nome} não pode executar - condições não atendidas")
        
        return campanhas_validas
    
    def mostrar_info_campanha(self, campanha):
        """Mostra informações da campanha"""
        tipo_display = {
            'unico': 'Envio Único',
            'diario': 'Diário',
            'semanal': 'Semanal', 
            'mensal': 'Mensal',
            'personalizado': 'Personalizado (Cron)'
        }.get(campanha.tipo_agendamento, campanha.tipo_agendamento)
        
        fonte = 'SQL' if campanha.template_sql else 'Manual'
        
        proxima_exec = campanha.proxima_execucao
        if campanha.tipo_agendamento == 'unico':
            proxima_exec = campanha.data_agendamento
        
        logger.info(f"  📧 {campanha.nome}")
        logger.info(f"     ID: {campanha.id}")
        logger.info(f"     Tipo: {tipo_display}")
        logger.info(f"     Fonte: {fonte}")
        if proxima_exec:
            proxima_brasilia = timezone.localtime(proxima_exec)
            logger.info(f"     Agendado para: {proxima_brasilia.strftime('%d/%m/%Y %H:%M')} (Brasília)")
    
    def executar_campanha(self, campanha, verbose=False):
        """
        Executa uma campanha específica
        
        IMPORTANTE: Este método executa o fluxo completo:
        1. Executa consultas SQL/API para obter dados atualizados
        2. Processa e atualiza dados dos clientes
        3. Envia emails com dados frescos
        4. Calcula próxima execução (se recorrente)
        """
        try:
            logger.info(f"🚀 Executando campanha: {campanha.nome}")
            
            # Marcar como executando
            campanha.status = 'executando'
            campanha.save(update_fields=['status'])
            
            # Executar usando o executor simplificado
            executor = ExecutorCampanhaSimplificado(campanha)
            sucesso = executor.executar()
            
            if sucesso:
                logger.info(f"✅ Campanha {campanha.nome} executada com sucesso")
                
                # Marcar execução como concluída e calcular próxima
                campanha.marcar_execucao_concluida()
                
                # Log da próxima execução para campanhas recorrentes
                if campanha.tipo_agendamento != 'unico' and campanha.proxima_execucao:
                    proxima_brasilia = timezone.localtime(campanha.proxima_execucao)
                    logger.info(f"📅 Próxima execução agendada para: {proxima_brasilia.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)")
                elif campanha.tipo_agendamento == 'unico':
                    logger.info(f"🏁 Campanha única finalizada")
                
                return True
            else:
                logger.error(f"❌ Falha na execução da campanha {campanha.nome}")
                campanha.status = 'erro'
                campanha.save(update_fields=['status'])
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao executar campanha {campanha.nome}: {str(e)}", exc_info=True)
            campanha.status = 'erro'
            campanha.save(update_fields=['status'])
            return False
