"""
Comando simplificado para executar campanhas de email
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from emails.models import CampanhaEmail
from emails.servico_simplificado import ExecutorCampanhaSimplificado


class Command(BaseCommand):
    help = 'Executa campanhas de email - VERSÃO SIMPLIFICADA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--id',
            type=int,
            help='ID específico da campanha para executar'
        )
        
        parser.add_argument(
            '--todas',
            action='store_true',
            help='Executar todas as campanhas agendadas'
        )
        
        parser.add_argument(
            '--teste',
            action='store_true',
            help='Modo teste - apenas mostra o que seria feito'
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 EXECUTOR SIMPLIFICADO DE CAMPANHAS EMAIL")
        self.stdout.write("=" * 50)
        
        if options['id']:
            # Executar campanha específica
            self.executar_campanha_especifica(options['id'], options['teste'])
            
        elif options['todas']:
            # Executar todas agendadas
            self.executar_todas_agendadas(options['teste'])
            
        else:
            # Mostrar ajuda
            self.mostrar_ajuda()

    def executar_campanha_especifica(self, campanha_id, modo_teste=False):
        """Executa uma campanha específica"""
        try:
            campanha = CampanhaEmail.objects.get(id=campanha_id)
            
            self.stdout.write(f"📧 Campanha: {campanha.nome}")
            self.stdout.write(f"🆔 ID: {campanha_id}")
            self.stdout.write(f"📊 Status: {campanha.get_status_display()}")
            
            if modo_teste:
                self.stdout.write("🧪 MODO TESTE - Nenhum email será enviado")
                # Aqui poderia simular a execução
                return
            
            if not campanha.pode_executar():
                self.stdout.write("❌ Campanha não pode ser executada")
                self.stdout.write(f"   Motivo: Status {campanha.get_status_display()}")
                return
            
            # Executar
            executor = ExecutorCampanhaSimplificado(campanha)
            sucesso = executor.executar()
            
            if sucesso:
                self.stdout.write("✅ Campanha executada com sucesso!")
            else:
                self.stdout.write("❌ Erro na execução da campanha")
                
        except CampanhaEmail.DoesNotExist:
            self.stdout.write(f"❌ Campanha {campanha_id} não encontrada")
        except Exception as e:
            self.stdout.write(f"❌ Erro: {e}")

    def executar_todas_agendadas(self, modo_teste=False):
        """Executa todas as campanhas agendadas"""
        agora = timezone.now()
        
        campanhas = CampanhaEmail.objects.filter(
            status='agendada',
            ativo=True,
            data_agendamento__lte=agora
        )
        
        self.stdout.write(f"🔍 Encontradas {campanhas.count()} campanha(s) para executar")
        
        if modo_teste:
            self.stdout.write("🧪 MODO TESTE - Listando campanhas:")
            for campanha in campanhas:
                self.stdout.write(f"  - {campanha.nome} (ID: {campanha.id})")
            return
        
        executadas = 0
        erros = 0
        
        for campanha in campanhas:
            try:
                self.stdout.write(f"🚀 Executando: {campanha.nome}")
                executor = ExecutorCampanhaSimplificado(campanha)
                
                if executor.executar():
                    executadas += 1
                    self.stdout.write(f"✅ {campanha.nome} - Sucesso")
                else:
                    erros += 1
                    self.stdout.write(f"❌ {campanha.nome} - Erro")
                    
            except Exception as e:
                erros += 1
                self.stdout.write(f"❌ {campanha.nome} - Erro: {e}")
        
        self.stdout.write("-" * 50)
        self.stdout.write(f"📊 Resumo: {executadas} sucesso(s), {erros} erro(s)")

    def mostrar_ajuda(self):
        """Mostra ajuda de uso"""
        self.stdout.write("📋 USO DO COMANDO:")
        self.stdout.write("")
        self.stdout.write("1️⃣  Executar campanha específica:")
        self.stdout.write("   python manage.py executar_email_simples --id=1")
        self.stdout.write("")
        self.stdout.write("2️⃣  Executar todas agendadas:")
        self.stdout.write("   python manage.py executar_email_simples --todas")
        self.stdout.write("")
        self.stdout.write("3️⃣  Modo teste (sem enviar emails):")
        self.stdout.write("   python manage.py executar_email_simples --id=1 --teste")
        self.stdout.write("")
        
        # Mostrar campanhas disponíveis
        campanhas = CampanhaEmail.objects.all()[:5]
        if campanhas:
            self.stdout.write("📋 Campanhas disponíveis:")
            for campanha in campanhas:
                self.stdout.write(f"   {campanha.id}: {campanha.nome} ({campanha.get_status_display()})")
        else:
            self.stdout.write("❌ Nenhuma campanha encontrada")
            self.stdout.write("   Crie uma campanha primeiro no admin ou interface web")
