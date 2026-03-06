"""
Comando Django para exportar e importar dados de configuração entre aplicações.

Este comando permite:
1. Exportar dados de configuração para um arquivo JSON
2. Importar dados de configuração de um arquivo JSON para outra aplicação
3. Manter os IDs idênticos entre as aplicações
4. Ser idempotente (pode executar múltiplas vezes, apenas atualiza/insere o que for novo)

Models exportados/importados:
- Configurações da API Matrix (MatrixAPIConfig)
- Configurações de Pagamento HSM (ConfiguracaoPagamentoHSM)
- Credenciais Hubsoft (CredenciaisHubsoft)
- Credenciais de Banco de Dados (CredenciaisBancoDados)
- Templates HSM (HSMTemplate)
- Templates SQL (TemplateSQL)
- Configurações dos Servidores de Email (ConfiguracaoServidorEmail)
- Templates de Email (TemplateEmail)

Uso:
    # Exportar dados
    python manage.py importar_dados_configuracao --export --arquivo dados_configuracao.json
    
    # Importar dados
    python manage.py importar_dados_configuracao --import --arquivo dados_configuracao.json
    
    # Modo verbose
    python manage.py importar_dados_configuracao --import --arquivo dados_configuracao.json --verbose
"""

import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from campanhas.models import (
    MatrixAPIConfig,
    ConfiguracaoPagamentoHSM,
    CredenciaisHubsoft,
    CredenciaisBancoDados,
    HSMTemplate,
    TemplateSQL,
)
from emails.models import (
    ConfiguracaoServidorEmail,
    TemplateEmail,
)


class Command(BaseCommand):
    help = 'Exporta e importa dados de configuração entre aplicações mantendo IDs idênticos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--export',
            action='store_true',
            help='Exporta dados para arquivo JSON',
        )
        parser.add_argument(
            '--import',
            dest='import_data',
            action='store_true',
            help='Importa dados de arquivo JSON',
        )
        parser.add_argument(
            '--arquivo',
            type=str,
            default='dados_configuracao.json',
            help='Caminho do arquivo JSON para exportar/importar (padrão: dados_configuracao.json)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostra informações detalhadas durante a execução',
        )

    def handle(self, *args, **options):
        export = options['export']
        import_data = options['import_data']
        arquivo = options['arquivo']
        verbose = options['verbose']

        if not export and not import_data:
            self.stdout.write(
                self.style.ERROR('Você deve especificar --export ou --import')
            )
            return

        if export:
            self.exportar_dados(arquivo, verbose)
        elif import_data:
            self.importar_dados(arquivo, verbose)

    def exportar_dados(self, arquivo, verbose):
        """Exporta todos os dados de configuração para um arquivo JSON"""
        self.stdout.write(self.style.SUCCESS('🔄 Iniciando exportação de dados...'))
        
        dados_exportados = {
            'data_exportacao': timezone.now().isoformat(),
            'versao': '1.0',
            'dados': {}
        }

        # 1. Configurações da API Matrix
        if verbose:
            self.stdout.write('  📦 Exportando Configurações da API Matrix...')
        dados_exportados['dados']['matrix_api_config'] = []
        for obj in MatrixAPIConfig.objects.all().order_by('id'):
            dados_exportados['dados']['matrix_api_config'].append({
                'id': obj.id,
                'nome': obj.nome,
                'base_url': obj.base_url,
                'api_key': obj.api_key,
                'cod_conta': obj.cod_conta,
                'ativo': obj.ativo,
                'data_criacao': obj.data_criacao.isoformat() if obj.data_criacao else None,
                'data_atualizacao': obj.data_atualizacao.isoformat() if obj.data_atualizacao else None,
            })
        if verbose:
            self.stdout.write(f'    ✓ {len(dados_exportados["dados"]["matrix_api_config"])} configurações exportadas')

        # 2. Configurações de Pagamento HSM
        if verbose:
            self.stdout.write('  📦 Exportando Configurações de Pagamento HSM...')
        dados_exportados['dados']['configuracao_pagamento_hsm'] = []
        for obj in ConfiguracaoPagamentoHSM.objects.all().order_by('id'):
            dados_exportados['dados']['configuracao_pagamento_hsm'].append({
                'id': obj.id,
                'nome': obj.nome,
                'descricao': obj.descricao,
                'razao_social_empresa': obj.razao_social_empresa,
                'cnpj_empresa': obj.cnpj_empresa,
                'nome_produto_padrao': obj.nome_produto_padrao,
                'tipo_produto': obj.tipo_produto,
                'val_imposto': str(obj.val_imposto),
                'val_desconto': str(obj.val_desconto),
                'variaveis_flow_padrao': obj.variaveis_flow_padrao,
                'configuracao_extra': obj.configuracao_extra,
                'ativo': obj.ativo,
                'data_criacao': obj.data_criacao.isoformat() if obj.data_criacao else None,
                'data_atualizacao': obj.data_atualizacao.isoformat() if obj.data_atualizacao else None,
            })
        if verbose:
            self.stdout.write(f'    ✓ {len(dados_exportados["dados"]["configuracao_pagamento_hsm"])} configurações exportadas')

        # 3. Credenciais Hubsoft
        if verbose:
            self.stdout.write('  📦 Exportando Credenciais Hubsoft...')
        dados_exportados['dados']['credenciais_hubsoft'] = []
        for obj in CredenciaisHubsoft.objects.all().order_by('id'):
            dados_exportados['dados']['credenciais_hubsoft'].append({
                'id': obj.id,
                'titulo': obj.titulo,
                'client_id': obj.client_id,
                'client_secret': obj.client_secret,
                'username': obj.username,
                'password': obj.password,
                'url_base': str(obj.url_base),
                'url_token': str(obj.url_token),
                'ativo': obj.ativo,
                'data_criacao': obj.data_criacao.isoformat() if obj.data_criacao else None,
                'data_atualizacao': obj.data_atualizacao.isoformat() if obj.data_atualizacao else None,
            })
        if verbose:
            self.stdout.write(f'    ✓ {len(dados_exportados["dados"]["credenciais_hubsoft"])} credenciais exportadas')

        # 4. Credenciais de Banco de Dados
        if verbose:
            self.stdout.write('  📦 Exportando Credenciais de Banco de Dados...')
        dados_exportados['dados']['credenciais_banco_dados'] = []
        for obj in CredenciaisBancoDados.objects.all().order_by('id'):
            dados_exportados['dados']['credenciais_banco_dados'].append({
                'id': obj.id,
                'titulo': obj.titulo,
                'tipo_banco': obj.tipo_banco,
                'host': obj.host,
                'porta': obj.porta,
                'banco': obj.banco,
                'usuario': obj.usuario,
                'senha': obj.senha,
                'ativo': obj.ativo,
                'data_criacao': obj.data_criacao.isoformat() if obj.data_criacao else None,
                'data_atualizacao': obj.data_atualizacao.isoformat() if obj.data_atualizacao else None,
            })
        if verbose:
            self.stdout.write(f'    ✓ {len(dados_exportados["dados"]["credenciais_banco_dados"])} credenciais exportadas')

        # 5. Templates HSM
        if verbose:
            self.stdout.write('  📦 Exportando Templates HSM...')
        dados_exportados['dados']['hsm_template'] = []
        for obj in HSMTemplate.objects.all().order_by('id'):
            dados_exportados['dados']['hsm_template'].append({
                'id': obj.id,
                'nome': obj.nome,
                'hsm_id': obj.hsm_id,
                'cod_flow': obj.cod_flow,
                'tipo_envio': obj.tipo_envio,
                'tipo_template': obj.tipo_template,
                'descricao': obj.descricao,
                'variaveis_descricao': obj.variaveis_descricao,
                'ativo': obj.ativo,
                'data_criacao': obj.data_criacao.isoformat() if obj.data_criacao else None,
                'data_atualizacao': obj.data_atualizacao.isoformat() if obj.data_atualizacao else None,
            })
        if verbose:
            self.stdout.write(f'    ✓ {len(dados_exportados["dados"]["hsm_template"])} templates exportados')

        # 6. Templates SQL
        if verbose:
            self.stdout.write('  📦 Exportando Templates SQL...')
        dados_exportados['dados']['template_sql'] = []
        for obj in TemplateSQL.objects.all().order_by('id'):
            dados_exportados['dados']['template_sql'].append({
                'id': obj.id,
                'consulta_sql': obj.consulta_sql,
                'titulo': obj.titulo,
                'descricao': obj.descricao,
                'variaveis_config': obj.variaveis_config,
                'ativo': obj.ativo,
                'data_criacao': obj.data_criacao.isoformat() if obj.data_criacao else None,
                'data_atualizacao': obj.data_atualizacao.isoformat() if obj.data_atualizacao else None,
            })
        if verbose:
            self.stdout.write(f'    ✓ {len(dados_exportados["dados"]["template_sql"])} templates exportados')

        # 7. Configurações dos Servidores de Email
        if verbose:
            self.stdout.write('  📦 Exportando Configurações dos Servidores de Email...')
        dados_exportados['dados']['configuracao_servidor_email'] = []
        for obj in ConfiguracaoServidorEmail.objects.all().order_by('id'):
            dados_exportados['dados']['configuracao_servidor_email'].append({
                'id': obj.id,
                'nome': obj.nome,
                'servidor_smtp': obj.servidor_smtp,
                'porta': obj.porta,
                'usuario': obj.usuario,
                'senha': obj.senha,
                'usar_tls': obj.usar_tls,
                'usar_ssl': obj.usar_ssl,
                'email_remetente': obj.email_remetente,
                'nome_remetente': obj.nome_remetente,
                'timeout': obj.timeout,
                'ativo': obj.ativo,
                'data_criacao': obj.data_criacao.isoformat() if obj.data_criacao else None,
                'data_atualizacao': obj.data_atualizacao.isoformat() if obj.data_atualizacao else None,
                'data_ultimo_teste': obj.data_ultimo_teste.isoformat() if obj.data_ultimo_teste else None,
                'resultado_ultimo_teste': obj.resultado_ultimo_teste,
            })
        if verbose:
            self.stdout.write(f'    ✓ {len(dados_exportados["dados"]["configuracao_servidor_email"])} configurações exportadas')

        # 8. Templates de Email
        if verbose:
            self.stdout.write('  📦 Exportando Templates de Email...')
        dados_exportados['dados']['template_email'] = []
        for obj in TemplateEmail.objects.all().order_by('id'):
            dados_exportados['dados']['template_email'].append({
                'id': obj.id,
                'nome': obj.nome,
                'tipo': obj.tipo,
                'assunto': obj.assunto,
                'corpo_html': obj.corpo_html,
                'corpo_texto': obj.corpo_texto,
                'css_personalizado': obj.css_personalizado,
                'variaveis_personalizadas': obj.variaveis_personalizadas,
                'descricao': obj.descricao,
                'ativo': obj.ativo,
                'total_enviados': obj.total_enviados,
                'total_sucessos': obj.total_sucessos,
                'total_erros': obj.total_erros,
                'data_criacao': obj.data_criacao.isoformat() if obj.data_criacao else None,
                'data_atualizacao': obj.data_atualizacao.isoformat() if obj.data_atualizacao else None,
                'data_ultimo_envio': obj.data_ultimo_envio.isoformat() if obj.data_ultimo_envio else None,
            })
        if verbose:
            self.stdout.write(f'    ✓ {len(dados_exportados["dados"]["template_email"])} templates exportados')

        # Salvar arquivo JSON
        try:
            with open(arquivo, 'w', encoding='utf-8') as f:
                json.dump(dados_exportados, f, ensure_ascii=False, indent=2)
            
            total_registros = sum(len(v) for v in dados_exportados['dados'].values())
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Exportação concluída com sucesso!\n'
                    f'   Arquivo: {arquivo}\n'
                    f'   Total de registros: {total_registros}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro ao salvar arquivo: {str(e)}')
            )
            raise

    @transaction.atomic
    def importar_dados(self, arquivo, verbose):
        """Importa dados de configuração de um arquivo JSON"""
        self.stdout.write(self.style.SUCCESS('🔄 Iniciando importação de dados...'))

        # Verificar se arquivo existe
        if not os.path.exists(arquivo):
            self.stdout.write(
                self.style.ERROR(f'❌ Arquivo não encontrado: {arquivo}')
            )
            return

        # Carregar dados do arquivo
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                dados_importados = json.load(f)
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro ao ler arquivo: {str(e)}')
            )
            raise

        if 'dados' not in dados_importados:
            self.stdout.write(
                self.style.ERROR('❌ Formato de arquivo inválido: chave "dados" não encontrada')
            )
            return

        dados = dados_importados['dados']
        total_importados = 0
        total_atualizados = 0
        total_erros = 0

        # 1. Importar Configurações da API Matrix
        if verbose:
            self.stdout.write('\n  📥 Importando Configurações da API Matrix...')
        for item in dados.get('matrix_api_config', []):
            try:
                obj, created = MatrixAPIConfig.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'nome': item['nome'],
                        'base_url': item['base_url'],
                        'api_key': item['api_key'],
                        'cod_conta': item['cod_conta'],
                        'ativo': item['ativo'],
                    }
                )
                if created:
                    total_importados += 1
                    if verbose:
                        self.stdout.write(f'    ✓ Criado: {obj.nome} (ID: {obj.id})')
                else:
                    total_atualizados += 1
                    if verbose:
                        self.stdout.write(f'    ↻ Atualizado: {obj.nome} (ID: {obj.id})')
            except Exception as e:
                total_erros += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Erro ao importar MatrixAPIConfig ID {item.get("id")}: {str(e)}')
                )

        # 2. Importar Configurações de Pagamento HSM
        if verbose:
            self.stdout.write('\n  📥 Importando Configurações de Pagamento HSM...')
        for item in dados.get('configuracao_pagamento_hsm', []):
            try:
                from decimal import Decimal
                obj, created = ConfiguracaoPagamentoHSM.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'nome': item['nome'],
                        'descricao': item.get('descricao', ''),
                        'razao_social_empresa': item['razao_social_empresa'],
                        'cnpj_empresa': item['cnpj_empresa'],
                        'nome_produto_padrao': item['nome_produto_padrao'],
                        'tipo_produto': item['tipo_produto'],
                        'val_imposto': Decimal(item['val_imposto']),
                        'val_desconto': Decimal(item['val_desconto']),
                        'variaveis_flow_padrao': item.get('variaveis_flow_padrao', {}),
                        'configuracao_extra': item.get('configuracao_extra', {}),
                        'ativo': item['ativo'],
                    }
                )
                if created:
                    total_importados += 1
                    if verbose:
                        self.stdout.write(f'    ✓ Criado: {obj.nome} (ID: {obj.id})')
                else:
                    total_atualizados += 1
                    if verbose:
                        self.stdout.write(f'    ↻ Atualizado: {obj.nome} (ID: {obj.id})')
            except Exception as e:
                total_erros += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Erro ao importar ConfiguracaoPagamentoHSM ID {item.get("id")}: {str(e)}')
                )

        # 3. Importar Credenciais Hubsoft
        if verbose:
            self.stdout.write('\n  📥 Importando Credenciais Hubsoft...')
        for item in dados.get('credenciais_hubsoft', []):
            try:
                obj, created = CredenciaisHubsoft.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'titulo': item['titulo'],
                        'client_id': item['client_id'],
                        'client_secret': item['client_secret'],
                        'username': item['username'],
                        'password': item['password'],
                        'url_base': item['url_base'],
                        'url_token': item['url_token'],
                        'ativo': item['ativo'],
                    }
                )
                if created:
                    total_importados += 1
                    if verbose:
                        self.stdout.write(f'    ✓ Criado: {obj.titulo} (ID: {obj.id})')
                else:
                    total_atualizados += 1
                    if verbose:
                        self.stdout.write(f'    ↻ Atualizado: {obj.titulo} (ID: {obj.id})')
            except Exception as e:
                total_erros += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Erro ao importar CredenciaisHubsoft ID {item.get("id")}: {str(e)}')
                )

        # 4. Importar Credenciais de Banco de Dados
        if verbose:
            self.stdout.write('\n  📥 Importando Credenciais de Banco de Dados...')
        for item in dados.get('credenciais_banco_dados', []):
            try:
                obj, created = CredenciaisBancoDados.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'titulo': item['titulo'],
                        'tipo_banco': item['tipo_banco'],
                        'host': item['host'],
                        'porta': item['porta'],
                        'banco': item['banco'],
                        'usuario': item['usuario'],
                        'senha': item['senha'],
                        'ativo': item['ativo'],
                    }
                )
                if created:
                    total_importados += 1
                    if verbose:
                        self.stdout.write(f'    ✓ Criado: {obj.titulo} (ID: {obj.id})')
                else:
                    total_atualizados += 1
                    if verbose:
                        self.stdout.write(f'    ↻ Atualizado: {obj.titulo} (ID: {obj.id})')
            except Exception as e:
                total_erros += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Erro ao importar CredenciaisBancoDados ID {item.get("id")}: {str(e)}')
                )

        # 5. Importar Templates HSM
        if verbose:
            self.stdout.write('\n  📥 Importando Templates HSM...')
        for item in dados.get('hsm_template', []):
            try:
                obj, created = HSMTemplate.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'nome': item['nome'],
                        'hsm_id': item['hsm_id'],
                        'cod_flow': item.get('cod_flow'),
                        'tipo_envio': item['tipo_envio'],
                        'tipo_template': item['tipo_template'],
                        'descricao': item.get('descricao', ''),
                        'variaveis_descricao': item.get('variaveis_descricao', {}),
                        'ativo': item['ativo'],
                    }
                )
                if created:
                    total_importados += 1
                    if verbose:
                        self.stdout.write(f'    ✓ Criado: {obj.nome} (ID: {obj.id})')
                else:
                    total_atualizados += 1
                    if verbose:
                        self.stdout.write(f'    ↻ Atualizado: {obj.nome} (ID: {obj.id})')
            except Exception as e:
                total_erros += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Erro ao importar HSMTemplate ID {item.get("id")}: {str(e)}')
                )

        # 6. Importar Templates SQL
        if verbose:
            self.stdout.write('\n  📥 Importando Templates SQL...')
        for item in dados.get('template_sql', []):
            try:
                obj, created = TemplateSQL.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'consulta_sql': item['consulta_sql'],
                        'titulo': item['titulo'],
                        'descricao': item.get('descricao'),
                        'variaveis_config': item.get('variaveis_config', {}),
                        'ativo': item['ativo'],
                    }
                )
                if created:
                    total_importados += 1
                    if verbose:
                        self.stdout.write(f'    ✓ Criado: {obj.titulo} (ID: {obj.id})')
                else:
                    total_atualizados += 1
                    if verbose:
                        self.stdout.write(f'    ↻ Atualizado: {obj.titulo} (ID: {obj.id})')
            except Exception as e:
                total_erros += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Erro ao importar TemplateSQL ID {item.get("id")}: {str(e)}')
                )

        # 7. Importar Configurações dos Servidores de Email
        if verbose:
            self.stdout.write('\n  📥 Importando Configurações dos Servidores de Email...')
        for item in dados.get('configuracao_servidor_email', []):
            try:
                from django.utils.dateparse import parse_datetime
                data_ultimo_teste = None
                if item.get('data_ultimo_teste'):
                    data_ultimo_teste = parse_datetime(item['data_ultimo_teste'])
                
                obj, created = ConfiguracaoServidorEmail.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'nome': item['nome'],
                        'servidor_smtp': item['servidor_smtp'],
                        'porta': item['porta'],
                        'usuario': item['usuario'],
                        'senha': item['senha'],
                        'usar_tls': item['usar_tls'],
                        'usar_ssl': item['usar_ssl'],
                        'email_remetente': item['email_remetente'],
                        'nome_remetente': item.get('nome_remetente', ''),
                        'timeout': item.get('timeout', 30),
                        'ativo': item['ativo'],
                        'data_ultimo_teste': data_ultimo_teste,
                        'resultado_ultimo_teste': item.get('resultado_ultimo_teste', ''),
                    }
                )
                if created:
                    total_importados += 1
                    if verbose:
                        self.stdout.write(f'    ✓ Criado: {obj.nome} (ID: {obj.id})')
                else:
                    total_atualizados += 1
                    if verbose:
                        self.stdout.write(f'    ↻ Atualizado: {obj.nome} (ID: {obj.id})')
            except Exception as e:
                total_erros += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Erro ao importar ConfiguracaoServidorEmail ID {item.get("id")}: {str(e)}')
                )

        # 8. Importar Templates de Email
        if verbose:
            self.stdout.write('\n  📥 Importando Templates de Email...')
        for item in dados.get('template_email', []):
            try:
                from django.utils.dateparse import parse_datetime
                data_ultimo_envio = None
                if item.get('data_ultimo_envio'):
                    data_ultimo_envio = parse_datetime(item['data_ultimo_envio'])
                
                obj, created = TemplateEmail.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'nome': item['nome'],
                        'tipo': item['tipo'],
                        'assunto': item['assunto'],
                        'corpo_html': item['corpo_html'],
                        'corpo_texto': item.get('corpo_texto', ''),
                        'css_personalizado': item.get('css_personalizado', ''),
                        'variaveis_personalizadas': item.get('variaveis_personalizadas', {}),
                        'descricao': item.get('descricao', ''),
                        'ativo': item['ativo'],
                        'total_enviados': item.get('total_enviados', 0),
                        'total_sucessos': item.get('total_sucessos', 0),
                        'total_erros': item.get('total_erros', 0),
                        'data_ultimo_envio': data_ultimo_envio,
                    }
                )
                if created:
                    total_importados += 1
                    if verbose:
                        self.stdout.write(f'    ✓ Criado: {obj.nome} (ID: {obj.id})')
                else:
                    total_atualizados += 1
                    if verbose:
                        self.stdout.write(f'    ↻ Atualizado: {obj.nome} (ID: {obj.id})')
            except Exception as e:
                total_erros += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Erro ao importar TemplateEmail ID {item.get("id")}: {str(e)}')
                )

        # Resumo final
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Importação concluída!\n'
                f'   ✓ Novos registros: {total_importados}\n'
                f'   ↻ Registros atualizados: {total_atualizados}\n'
                f'   ✗ Erros: {total_erros}'
            )
        )
