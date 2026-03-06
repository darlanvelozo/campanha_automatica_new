"""
Comando para testar conexões com bancos de dados configurados.
Útil para diagnosticar problemas de conectividade.
"""

from django.core.management.base import BaseCommand
from campanhas.models import CredenciaisBancoDados
import sys


class Command(BaseCommand):
    help = 'Testa conexão com bancos de dados configurados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--id',
            type=int,
            help='ID da credencial específica para testar',
        )
        parser.add_argument(
            '--tipo',
            type=str,
            help='Tipo de banco para testar (postgresql, mysql, clickhouse, etc)',
        )

    def handle(self, *args, **options):
        credencial_id = options.get('id')
        tipo_banco = options.get('tipo')
        
        # Filtrar credenciais
        if credencial_id:
            credenciais = CredenciaisBancoDados.objects.filter(id=credencial_id, ativo=True)
        elif tipo_banco:
            credenciais = CredenciaisBancoDados.objects.filter(tipo_banco=tipo_banco, ativo=True)
        else:
            credenciais = CredenciaisBancoDados.objects.filter(ativo=True)
        
        if not credenciais.exists():
            self.stdout.write(self.style.WARNING('Nenhuma credencial encontrada com os critérios fornecidos'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Testando {credenciais.count()} credenciai(s)...'))
        self.stdout.write('')
        
        sucesso = 0
        falhas = 0
        
        for credencial in credenciais:
            self.stdout.write(f'📊 Testando: {credencial.titulo} ({credencial.tipo_banco})')
            self.stdout.write(f'   Host: {credencial.host}:{credencial.porta}')
            self.stdout.write(f'   Database: {credencial.banco}')
            self.stdout.write(f'   User: {credencial.usuario}')
            
            try:
                resultado = self.testar_conexao(credencial)
                if resultado['sucesso']:
                    self.stdout.write(self.style.SUCCESS(f'   ✓ SUCESSO: {resultado["mensagem"]}'))
                    sucesso += 1
                else:
                    self.stdout.write(self.style.ERROR(f'   ✗ FALHA: {resultado["mensagem"]}'))
                    falhas += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ✗ ERRO: {str(e)}'))
                falhas += 1
            
            self.stdout.write('')
        
        # Resumo
        self.stdout.write('='*60)
        self.stdout.write(self.style.SUCCESS(f'✓ Sucessos: {sucesso}'))
        if falhas > 0:
            self.stdout.write(self.style.ERROR(f'✗ Falhas: {falhas}'))
        self.stdout.write('='*60)

    def testar_conexao(self, credencial):
        """Testa a conexão com o banco de dados"""
        
        try:
            if credencial.tipo_banco == 'postgresql':
                import psycopg2
                conn = psycopg2.connect(
                    host=credencial.host,
                    port=credencial.porta,
                    database=credencial.banco,
                    user=credencial.usuario,
                    password=credencial.senha,
                    connect_timeout=5
                )
                cursor = conn.cursor()
                cursor.execute('SELECT version();')
                version = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                return {'sucesso': True, 'mensagem': f'PostgreSQL conectado - {version[:50]}...'}
                
            elif credencial.tipo_banco == 'clickhouse':
                from clickhouse_driver import Client
                
                client = Client(
                    host=credencial.host,
                    port=credencial.porta,
                    database=credencial.banco,
                    user=credencial.usuario,
                    password=credencial.senha,
                    connect_timeout=10,
                    send_receive_timeout=30
                )
                
                # Testa conexão com query simples
                result = client.execute('SELECT version()')
                version = result[0][0] if result else 'desconhecida'
                
                # Testa se consegue acessar o database
                result = client.execute(f'SELECT count() FROM system.tables WHERE database = \'{credencial.banco}\'')
                num_tables = result[0][0]
                
                return {
                    'sucesso': True, 
                    'mensagem': f'ClickHouse v{version} - Database com {num_tables} tabelas'
                }
                
            elif credencial.tipo_banco == 'mysql':
                import mysql.connector
                conn = mysql.connector.connect(
                    host=credencial.host,
                    port=credencial.porta,
                    database=credencial.banco,
                    user=credencial.usuario,
                    password=credencial.senha,
                    connect_timeout=5
                )
                cursor = conn.cursor()
                cursor.execute('SELECT VERSION();')
                version = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                return {'sucesso': True, 'mensagem': f'MySQL conectado - {version}'}
                
            elif credencial.tipo_banco == 'sqlserver':
                import pyodbc
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={credencial.host},{credencial.porta};"
                    f"DATABASE={credencial.banco};"
                    f"UID={credencial.usuario};"
                    f"PWD={credencial.senha};"
                    f"Connection Timeout=5;"
                )
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                cursor.execute('SELECT @@VERSION;')
                version = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                return {'sucesso': True, 'mensagem': f'SQL Server conectado - {version[:50]}...'}
                
            elif credencial.tipo_banco == 'oracle':
                import cx_Oracle
                dsn = cx_Oracle.makedsn(
                    credencial.host,
                    credencial.porta,
                    service_name=credencial.banco
                )
                conn = cx_Oracle.connect(
                    user=credencial.usuario,
                    password=credencial.senha,
                    dsn=dsn
                )
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM v$version WHERE rownum = 1')
                version = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                return {'sucesso': True, 'mensagem': f'Oracle conectado - {version}'}
                
            else:
                return {'sucesso': False, 'mensagem': f'Tipo de banco não suportado: {credencial.tipo_banco}'}
                
        except Exception as e:
            return {'sucesso': False, 'mensagem': f'{type(e).__name__}: {str(e)}'}
