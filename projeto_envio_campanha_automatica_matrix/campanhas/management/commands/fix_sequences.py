"""
Comando para sincronizar as sequências do PostgreSQL com os dados existentes.

IMPORTANTE: Este comando NÃO altera nenhum dado existente!
Ele apenas ajusta a sequência para apontar para o próximo ID disponível,
garantindo que novos registros não causem conflito de chave primária.

Os IDs existentes permanecem intactos e inalterados.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Sincroniza as sequências do PostgreSQL sem alterar dados existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--table',
            type=str,
            help='Nome específico da tabela para sincronizar (opcional)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria feito, sem fazer alterações',
        )

    def handle(self, *args, **options):
        table_name = options.get('table')
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: Nenhuma alteração será feita'))
            self.stdout.write('')
        
        with connection.cursor() as cursor:
            if table_name:
                # Sincronizar apenas uma tabela específica
                self.sync_sequence_for_table(cursor, table_name, dry_run)
            else:
                # Sincronizar todas as tabelas do app campanhas
                tables = [
                    'campanhas_templatesql',
                    'campanhas_variaveltemplate',
                    'campanhas_credencialbanco',
                    'campanhas_credencialhubsoft',
                    'campanhas_campanha',
                    'campanhas_execucaocampanha',
                    'campanhas_clienteconsultado',
                    'campanhas_clienteenviado',
                    'campanhas_hsmtemplate',
                    'campanhas_enviohsmmatrix',
                    'campanhas_enviohsmindividual',
                    'campanhas_configuracaopagamentohsm',
                    'campanhas_matrixapiconfig',
                    'campanhas_consultaexecucao',
                    'campanhas_consultacliente',
                ]
                
                self.stdout.write(self.style.SUCCESS('Sincronizando sequências do PostgreSQL...'))
                self.stdout.write(self.style.WARNING('⚠️  NENHUM DADO EXISTENTE SERÁ ALTERADO'))
                self.stdout.write('')
                
                for table in tables:
                    self.sync_sequence_for_table(cursor, table, dry_run)
                
                self.stdout.write('')
                if not dry_run:
                    self.stdout.write(self.style.SUCCESS('✓ Todas as sequências foram sincronizadas!'))
                    self.stdout.write('Agora você pode adicionar novos registros sem conflito de IDs.')
                else:
                    self.stdout.write(self.style.SUCCESS('✓ Análise concluída (modo dry-run)'))

    def sync_sequence_for_table(self, cursor, table_name, dry_run=False):
        """
        Sincroniza a sequência de uma tabela específica.
        
        IMPORTANTE: Esta operação NÃO modifica registros existentes!
        Apenas ajusta o contador da sequência para o próximo valor disponível.
        """
        try:
            # Primeiro, verificar o valor atual da sequência
            sequence_name_query = f"SELECT pg_get_serial_sequence('{table_name}', 'id')"
            cursor.execute(sequence_name_query)
            seq_result = cursor.fetchone()
            
            if not seq_result or not seq_result[0]:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠ {table_name}: não possui sequência de auto-incremento')
                )
                return
            
            sequence_name = seq_result[0]
            
            # Obter o valor atual da sequência
            cursor.execute(f"SELECT last_value FROM {sequence_name}")
            current_seq = cursor.fetchone()
            current_value = current_seq[0] if current_seq else 0
            
            # Verificar o maior ID existente na tabela
            cursor.execute(f"SELECT MAX(id) FROM {table_name}")
            max_id_result = cursor.fetchone()
            max_id = max_id_result[0] if max_id_result and max_id_result[0] else 0
            
            # Calcular o próximo valor da sequência
            next_value = max_id + 1
            
            if current_value >= next_value:
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ {table_name}: sequência OK (valor atual: {current_value}, máximo ID: {max_id})')
                )
            else:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠ {table_name}: sequência DESATUALIZADA')
                    )
                    self.stdout.write(f'      Valor atual da sequência: {current_value}')
                    self.stdout.write(f'      Maior ID na tabela: {max_id}')
                    self.stdout.write(f'      Seria ajustado para: {next_value}')
                else:
                    # Ajustar a sequência para o próximo valor disponível
                    # setval com 'false' como terceiro parâmetro define o valor que será retornado no PRÓXIMO nextval()
                    cursor.execute(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table_name}', 'id'),
                            {max_id},
                            true
                        );
                    """)
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ {table_name}: sequência sincronizada')
                    )
                    self.stdout.write(f'      Maior ID existente: {max_id}')
                    self.stdout.write(f'      Próximo ID disponível: {next_value}')
                    self.stdout.write(f'      ⚠️  NENHUM registro existente foi alterado!')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ✗ {table_name}: Erro ao sincronizar - {str(e)}')
            )
