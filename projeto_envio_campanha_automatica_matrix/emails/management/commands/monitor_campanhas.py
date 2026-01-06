#!/usr/bin/env python3
"""
Comando Django para monitorar campanhas de email continuamente.
Este comando fica executando em loop, verificando campanhas que devem ser executadas.
"""

import time
import signal
import sys
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from emails.models import CampanhaEmail
from emails.servico_simplificado import ServicoEmailSimplificado

# Configurar logging
import os
from pathlib import Path

# Criar diretório de logs se não existir
log_dir = Path('/var/log/campanha_monitor')
log_dir.mkdir(exist_ok=True, mode=0o755)

# Configurar logging com rotação
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            '/var/log/campanha_monitor/monitor.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        ),
        RotatingFileHandler(
            '/tmp/monitor_campanhas.log',
            maxBytes=5*1024*1024,   # 5MB
            backupCount=3
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitora campanhas de email continuamente e executa quando necessário'
    
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
            '--dry-run',
            action='store_true',
            help='Apenas mostra quais campanhas seriam executadas, sem executar de fato',
        )
    
    def handle(self, *args, **options):
        self.check_interval = options['interval']
        verbose = options['verbose']
        dry_run = options['dry_run']
        
        # Configurar handler para SIGTERM e SIGINT
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        logger.info(f"🚀 Iniciando monitor de campanhas (intervalo: {self.check_interval}s)")
        if dry_run:
            logger.info("🔍 Modo DRY RUN ativado - nenhuma campanha será executada")
        
        try:
            while self.running:
                self.verificar_campanhas(verbose, dry_run)
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
    
    def verificar_campanhas(self, verbose=False, dry_run=False):
        """Verifica e executa campanhas que devem ser executadas agora"""
        agora = timezone.now()
        
        if verbose:
            logger.info(f"🔍 Verificando campanhas - {agora.strftime('%d/%m/%Y %H:%M:%S')}")
        
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
                logger.error(f"❌ Erro ao processar campanha {campanha.id} ({campanha.nome}): {str(e)}")
        
        # Resumo
        if dry_run:
            logger.info(f"✅ DRY RUN: {campanhas_executadas} campanha(s) seriam executadas")
        else:
            logger.info(f"✅ Execução concluída: {campanhas_executadas} executada(s), {campanhas_com_erro} com erro")
    
    def buscar_campanhas_para_execucao(self, agora):
        """Busca campanhas que devem ser executadas agora"""
        campanhas = CampanhaEmail.objects.filter(
            ativo=True,
            status__in=['agendada', 'rascunho']
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
                    
            elif campanha.tipo_agendamento in ['diario', 'semanal', 'mensal', 'personalizado']:
                # Campanhas recorrentes
                if campanha.ativa_recorrencia and campanha.deve_executar_agora():
                    deve_executar = True
            
            if deve_executar:
                # Verificar se não passou do fim da recorrência
                if campanha.data_fim_recorrencia and agora > campanha.data_fim_recorrencia:
                    # Desativar campanha que passou do prazo
                    campanha.ativa_recorrencia = False
                    campanha.status = 'concluida'
                    campanha.save(update_fields=['ativa_recorrencia', 'status'])
                    logger.info(f"⏰ Campanha {campanha.nome} finalizada (passou do prazo)")
                    continue
                
                campanhas_validas.append(campanha)
        
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
            logger.info(f"     Agendado para: {proxima_exec.strftime('%d/%m/%Y %H:%M')}")
    
    def executar_campanha(self, campanha, verbose=False):
        """Executa uma campanha específica"""
        try:
            logger.info(f"🚀 Executando campanha: {campanha.nome}")
            
            # Marcar como executando
            campanha.status = 'executando'
            campanha.save(update_fields=['status'])
            
            # Executar usando o serviço simplificado
            servico = ServicoEmailSimplificado(campanha)
            sucesso = servico.executar_campanha()
            
            if sucesso:
                logger.info(f"✅ Campanha {campanha.nome} executada com sucesso")
                
                # Marcar execução como concluída e calcular próxima
                campanha.marcar_execucao_concluida()
                
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
