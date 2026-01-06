from django.core.management.base import BaseCommand
from django.utils import timezone
from emails.services import GerenciadorCampanhaEmail
from emails.models import CampanhaEmail, LogEnvioEmail
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executa campanhas de email agendadas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--campanha-id',
            type=int,
            help='ID de uma campanha específica para executar'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas simula a execução sem enviar emails'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Saída mais detalhada'
        )

    def handle(self, *args, **options):
        verboso = options['verbose']
        dry_run = options['dry_run']
        campanha_id = options.get('campanha_id')

        if verboso:
            self.stdout.write(
                f"Iniciando execução de campanhas de email em {timezone.now()}"
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("MODO DRY-RUN: Nenhum email será enviado")
            )

        try:
            if campanha_id:
                # Executar campanha específica
                self._executar_campanha_especifica(campanha_id, dry_run, verboso)
            else:
                # Executar todas as campanhas agendadas
                self._executar_campanhas_agendadas(dry_run, verboso)

        except Exception as e:
            error_msg = f"Erro durante execução: {str(e)}"
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg)
            raise

    def _executar_campanha_especifica(self, campanha_id, dry_run, verboso):
        """Executa uma campanha específica"""
        try:
            campanha = CampanhaEmail.objects.get(id=campanha_id)
            
            if verboso:
                self.stdout.write(f"Executando campanha: {campanha.nome}")

            if not campanha.pode_executar():
                self.stdout.write(
                    self.style.WARNING(
                        f"Campanha {campanha.nome} não pode ser executada. "
                        f"Status: {campanha.get_status_display()}"
                    )
                )
                return

            if dry_run:
                self._simular_execucao(campanha, verboso)
            else:
                gerenciador = GerenciadorCampanhaEmail(campanha)
                sucesso = gerenciador.executar_envios()
                
                if sucesso:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Campanha {campanha.nome} executada com sucesso"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Erro ao executar campanha {campanha.nome}"
                        )
                    )

        except CampanhaEmail.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Campanha com ID {campanha_id} não encontrada")
            )

    def _executar_campanhas_agendadas(self, dry_run, verboso):
        """Executa todas as campanhas agendadas"""
        agora = timezone.now()
        
        campanhas_agendadas = CampanhaEmail.objects.filter(
            status='agendada',
            ativo=True,
            data_agendamento__lte=agora
        ).exclude(
            data_fim_recorrencia__lt=agora
        )

        if not campanhas_agendadas.exists():
            self.stdout.write("Nenhuma campanha agendada para execução")
            return

        if verboso:
            self.stdout.write(
                f"Encontradas {campanhas_agendadas.count()} campanha(s) agendada(s)"
            )

        executadas = 0
        erros = 0

        for campanha in campanhas_agendadas:
            try:
                if verboso:
                    self.stdout.write(f"Processando: {campanha.nome}")

                if not campanha.pode_executar():
                    if verboso:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Campanha {campanha.nome} pulada - "
                                f"condições não atendidas"
                            )
                        )
                    continue

                if dry_run:
                    self._simular_execucao(campanha, verboso)
                    executadas += 1
                else:
                    gerenciador = GerenciadorCampanhaEmail(campanha)
                    sucesso = gerenciador.executar_envios()
                    
                    if sucesso:
                        executadas += 1
                        if verboso:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"✓ {campanha.nome} executada com sucesso"
                                )
                            )
                    else:
                        erros += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"✗ Erro ao executar {campanha.nome}"
                            )
                        )

            except Exception as e:
                erros += 1
                error_msg = f"Erro ao processar campanha {campanha.nome}: {str(e)}"
                self.stdout.write(self.style.ERROR(error_msg))
                logger.error(error_msg)
                
                # Registrar erro no log
                LogEnvioEmail.criar_log(
                    'error',
                    'comando_execucao',
                    error_msg,
                    campanha=campanha
                )

        # Resumo final
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY-RUN: {executadas} campanha(s) seriam executadas"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Execução concluída: {executadas} sucesso(s), {erros} erro(s)"
                )
            )

    def _simular_execucao(self, campanha, verboso):
        """Simula a execução de uma campanha (dry-run)"""
        gerenciador = GerenciadorCampanhaEmail(campanha)
        
        # Preparar dados sem criar envios
        dados_clientes = gerenciador.preparar_dados_clientes()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"DRY-RUN - {campanha.nome}: "
                f"{len(dados_clientes)} email(s) seriam enviados"
            )
        )
        
        if verboso and dados_clientes:
            self.stdout.write("Primeiros 5 destinatários:")
            for i, dados in enumerate(dados_clientes[:5]):
                email = dados.get('email_destinatario', 'N/A')
                nome = dados.get('nome_destinatario', 'N/A')
                self.stdout.write(f"  {i+1}. {nome} <{email}>")
            
            if len(dados_clientes) > 5:
                self.stdout.write(f"  ... e mais {len(dados_clientes) - 5}")

    def _log_command_execution(self, message, level='info'):
        """Registra a execução do comando no log"""
        LogEnvioEmail.criar_log(
            level,
            'comando_execucao',
            message
        )
