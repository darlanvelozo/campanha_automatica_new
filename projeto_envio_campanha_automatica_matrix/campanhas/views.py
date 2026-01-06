# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db import connection
from django.utils import timezone
from django.urls import reverse 
import json
import pandas as pd
import unicodedata
import time
import logging
from io import StringIO
import threading
import requests
from datetime import date, datetime
from decimal import Decimal

def serializar_valor_para_json(valor):
    """Converte valores para formato JSON-serializável"""
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    elif isinstance(valor, Decimal):
        return float(valor)
    elif hasattr(valor, '__dict__'):
        return str(valor)
    return valor

def serializar_dados_dinamicos(dados):
    """Serializa dados dinâmicos para JSON"""
    if not dados:
        return {}
    
    dados_serializados = {}
    for chave, valor in dados.items():
        dados_serializados[chave] = serializar_valor_para_json(valor)
    
    return dados_serializados
from .models import (
    TemplateSQL, CredenciaisBancoDados, CredenciaisHubsoft, 
    ConsultaExecucao, ClienteConsultado, ConsultaCliente,
    MatrixAPIConfig, HSMTemplate, EnvioHSMMatrix, EnvioHSMIndividual,
    ConfiguracaoPagamentoHSM
)
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

def normalizar_texto(texto: str) -> str:
    """Normaliza o texto removendo acentos e convertendo para maiúsculas."""
    if not isinstance(texto, str):
        return ''
    nfkd_form = unicodedata.normalize('NFD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).upper()

class HubsoftAPI:
    def __init__(self, credenciais):
        self.credenciais = credenciais
        self._access_token = None
        self.session = requests.Session()
        self.timeout = 60

    def _get_token(self):
        """Obtém um novo token de acesso da API e o armazena."""
        logger.info(f"Solicitando novo token de acesso para {self.credenciais.url_base}")
        auth_payload = {
            "client_id": self.credenciais.client_id,
            "client_secret": self.credenciais.client_secret,
            "username": self.credenciais.username,
            "password": self.credenciais.password,
            "grant_type": "password"
        }
        try:
            response = requests.post(
                self.credenciais.url_token,
                json=auth_payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data.get('access_token')
            
            if not self._access_token:
                logger.error("Token de acesso não encontrado na resposta da API.")
                raise ValueError("Falha ao obter token: 'access_token' ausente na resposta.")
            
            self.session.headers.update({
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json'
            })
            logger.info("Token obtido e sessão configurada com sucesso.")

        except requests.RequestException as e:
            logger.error(f"Erro de rede ao obter token: {e}")
            raise

    def _ensure_token(self):
        """Garante que um token de acesso válido exista antes de fazer uma chamada."""
        if not self._access_token:
            self._get_token()

    def consultar_cliente_financeiro(self, codigo_cliente):
        """Consulta dados financeiros do cliente na API"""
        try:
            self._ensure_token()
            
            endpoint = f"/api/v1/integracao/cliente/financeiro?busca=codigo_cliente&termo_busca={codigo_cliente}"
            url = f"{self.credenciais.url_base}{endpoint}"
            
            logger.info(f"Consultando cliente {codigo_cliente}")
            
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            logger.info(f"Resposta da consulta para {codigo_cliente}: Status {response.status_code}")
            return response.json()

        except requests.RequestException as e:
            logger.error(f"Erro na consulta do cliente {codigo_cliente}: {e}")
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 401:
                logger.warning("Recebido status 401. O token pode ter expirado. Tentando obter um novo na próxima chamada.")
                self._access_token = None
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao consultar cliente {codigo_cliente}: {e}")
            return None

def pagina_processar_consulta(request):
    """Página principal para configurar e executar consultas"""
    templates = TemplateSQL.objects.filter(ativo=True)
    credenciais_hubsoft = CredenciaisHubsoft.objects.filter(ativo=True)
    credenciais_banco = CredenciaisBancoDados.objects.filter(ativo=True)
    
    context = {
        'templates_sql': templates,
        'credenciais_hubsoft': credenciais_hubsoft,
        'credenciais_banco': credenciais_banco
    }
    
    return render(request, 'campanhas/processar_consulta.html', context)

def obter_variaveis_template(request, template_id):
    """Retorna as variáveis de um template específico via AJAX"""
    try:
        template = TemplateSQL.objects.get(id=template_id, ativo=True)
        variaveis = template.get_variaveis_configuradas()
        
        return JsonResponse({
            'status': 'success',
            'variaveis': variaveis,
            'template_titulo': template.titulo
        })
    except TemplateSQL.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Template não encontrado'
        }, status=404)
    except Exception as e:
        logger.error(f"Erro ao obter variáveis do template {template_id}: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=500)

def executar_consulta_sql(credencial_banco, template_sql, valores_variaveis=None):
    """Executa uma consulta SQL no banco especificado, processando variáveis se necessário"""
    try:
        # Processa a query substituindo variáveis se fornecidas
        print(f"🔍 DEBUG EXECUTAR_CONSULTA_SQL:")
        print(f"  - valores_variaveis: {valores_variaveis}")
        print(f"  - template_sql tipo: {type(template_sql)}")
        print(f"  - hasattr substituir_variaveis: {hasattr(template_sql, 'substituir_variaveis')}")
        
        if valores_variaveis and hasattr(template_sql, 'substituir_variaveis'):
            print(f"🔧 CHAMANDO substituir_variaveis com: {valores_variaveis}")
            query = template_sql.substituir_variaveis(valores_variaveis)
            print(f"🔧 RESULTADO da substituição (últimas 100 chars): ...{query[-100:]}")
        else:
            print(f"❌ NÃO chamando substituir_variaveis - condição falhou")
            query = template_sql.consulta_sql if hasattr(template_sql, 'consulta_sql') else template_sql
        
        # Limpa a query preservando a estrutura SQL
        query = query.strip()
        
        # Log detalhado para debug
        logger.info(f"Executando consulta SQL com credencial: {credencial_banco.titulo}")
        logger.info(f"Query SQL original (primeiros 500 chars): {template_sql.consulta_sql[:500]}...")
        if valores_variaveis:
            logger.info(f"Variáveis utilizadas: {valores_variaveis}")
        logger.info(f"Query SQL processada (primeiros 500 chars): {query[:500]}...")
        logger.info(f"Tamanho da query: {len(query)} caracteres")
        
        # Conectar ao PostgreSQL
        conn = psycopg2.connect(
            host=credencial_banco.host,
            port=credencial_banco.porta,
            database=credencial_banco.banco,
            user=credencial_banco.usuario,
            password=credencial_banco.senha
        )
        
        # Configurar o cursor para retornar dicionários
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Executa a query como um bloco completo
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Converte para lista de dicionários
        results = [dict(row) for row in results]
        
        logger.info(f"Consulta SQL executada com sucesso. {len(results)} registros encontrados.")
        
        cursor.close()
        conn.close()
        
        return results
    except Exception as e:
        logger.error(f"Erro ao executar consulta SQL: {str(e)}")
        logger.error(f"Query que causou o erro: {query}")
        raise

def obter_fatura_por_id(dados: dict, id_fatura: str) -> dict | None:
    """Obtém uma fatura específica pelo ID dentro dos dados do cliente."""
    if not dados or 'faturas' not in dados:
        return None
    for fatura in dados.get('faturas', []):
        if str(fatura.get('id_fatura')) == str(id_fatura):
            return fatura
    return None

def converter_data_br_para_iso(data_str):
    """Converte data do formato DD/MM/YYYY para YYYY-MM-DD"""
    if not data_str:
        return None
    try:
        from datetime import datetime
        data = datetime.strptime(data_str, '%d/%m/%Y')
        return data.strftime('%Y-%m-%d')
    except Exception as e:
        logger.error(f"Erro ao converter data {data_str}: {e}")
        return None

def processar_cliente_api(api_client, cliente_data, execucao):
    """Processa um cliente individual - com ou sem consulta da API"""
    codigo_cliente = cliente_data.get('codigo_cliente')
    id_fatura_desejada = cliente_data.get('id_fatura')
    
    print("\n" + "="*80)
    if execucao.pular_consulta_api:
        print("📋 PROCESSANDO CLIENTE (APENAS DADOS SQL)")
    else:
        print("📡 PROCESSANDO CLIENTE VIA API")
    print("="*80)
    print(f"�� Código do Cliente: {codigo_cliente}")
    print(f"🏷️  ID da Fatura: {id_fatura_desejada}")
    print(f"�� Empresa: {execucao.credencial_banco.titulo if execucao.credencial_banco else 'N/A'}")
    print(f"🔄 Consultar API: {'NÃO' if execucao.pular_consulta_api else 'SIM'}")
    print("-"*80)
    
    # Garantir que sempre temos um cliente registrado, mesmo com erro
    cliente_obj = None
    error_msg = None
    dados_cliente = None
    fatura = None
    
    try:
        # Decide se consulta a API ou não
        if execucao.pular_consulta_api:
            print("⏭️  PULANDO CONSULTA NA API (configurado na execução)")
            print("📊 Usando apenas dados do template SQL")
            dados_cliente = None
            fatura = None
        else:
            # Verifica se tem credencial Hubsoft quando API é necessária
            if not execucao.credencial_hubsoft:
                error_msg = "Credencial Hubsoft é obrigatória quando a consulta da API está habilitada"
                print(f"❌ ERRO: {error_msg}")
                raise Exception(error_msg)
        # Consulta a API
        print("🔍 CONSULTANDO API HUBSOFT...")
        dados_cliente = api_client.consultar_cliente_financeiro(codigo_cliente)
        
        if not dados_cliente:
            error_msg = "Falha ao consultar dados na API - resposta vazia ou erro de conexão"
            print(f"❌ ERRO: {error_msg}")
            raise Exception(error_msg)
        
        print("✅ API consultada com sucesso")
        print(f"📊 Dados retornados: {len(str(dados_cliente))} caracteres")
        
        # Busca a fatura específica
        print(f"🔍 BUSCANDO FATURA {id_fatura_desejada}...")
        fatura = obter_fatura_por_id(dados_cliente, id_fatura_desejada)
        
        if not fatura:
            error_msg = f"Fatura {id_fatura_desejada} não encontrada nos dados retornados pela API"
            print(f"❌ ERRO: {error_msg}")
            raise Exception(error_msg)
        
        print("✅ Fatura encontrada na API")
        print(f"💰 Valor: R$ {fatura.get('valor', 'N/A')}")
        print(f"📅 Vencimento: {fatura.get('data_vencimento', 'N/A')}")
        
        # Cria ou atualiza o cliente consultado
        print("💾 SALVANDO/ATUALIZANDO CLIENTE...")
        cliente_obj, created = ClienteConsultado.objects.get_or_create(
            codigo_cliente=codigo_cliente,
            credencial_banco=execucao.credencial_banco,
            defaults={
                'nome_razaosocial': normalizar_texto(cliente_data.get('nome_razaosocial', '')),
                'telefone_corrigido': cliente_data.get('TelefoneCorrigido', '') or cliente_data.get('telefonecorrigido', ''),
                'id_fatura': id_fatura_desejada,
                'data_criacao': timezone.now()
            }
        )
        
        status_cliente = "CRIADO" if created else "ATUALIZADO"
        print(f"✅ Cliente {status_cliente}: {cliente_obj.codigo_cliente}")
        
        # Processa dados da fatura se API foi consultada
        data_vencimento = None
        if fatura:
            data_vencimento = fatura.get('data_vencimento')
        if data_vencimento:
            data_vencimento = converter_data_br_para_iso(data_vencimento)
            print(f"�� Data convertida: {data_vencimento}")
        
        # ATUALIZA TODOS OS DADOS DO CLIENTE a cada consulta
        print("🔄 ATUALIZANDO DADOS DO CLIENTE...")
        cliente_obj.nome_razaosocial = normalizar_texto(cliente_data.get('nome_razaosocial', ''))
        cliente_obj.telefone_corrigido = cliente_data.get('TelefoneCorrigido', '') or cliente_data.get('telefonecorrigido', '')
        cliente_obj.data_atualizacao = timezone.now()
        
        # Atualiza dados da fatura apenas se API foi consultada
        if not execucao.pular_consulta_api and fatura:
            cliente_obj.vencimento_fatura = data_vencimento
            cliente_obj.valor_fatura = fatura.get('valor')
            cliente_obj.pix = fatura.get('pix_copia_cola')
            cliente_obj.codigo_barras = fatura.get('linha_digitavel')
            cliente_obj.link_boleto = fatura.get('link')
            cliente_obj.id_fatura = id_fatura_desejada
            print("💳 Dados financeiros atualizados da API")
        else:
            # Mantém dados da fatura do SQL ou valores do cliente_data
            if id_fatura_desejada:
                cliente_obj.id_fatura = id_fatura_desejada
            if cliente_data.get('valor'):
                cliente_obj.valor_fatura = cliente_data.get('valor')
            if cliente_data.get('data_vencimento'):
                cliente_obj.vencimento_fatura = converter_data_br_para_iso(cliente_data.get('data_vencimento'))
            print("📊 Usando apenas dados do template SQL")
        
        # NOVO: Processa dados dinâmicos automaticamente dos templates SQL
        print("🔄 PROCESSANDO DADOS DINÂMICOS DOS TEMPLATES SQL...")
        
        # Usa a função utilitária para extrair dados dinâmicos
        from .utils import extrair_dados_dinamicos_sql
        dados_dinamicos = extrair_dados_dinamicos_sql(cliente_data, dados_cliente)
        
        # Salva os dados dinâmicos no cliente
        if dados_dinamicos:
            # Serializar dados dinâmicos para evitar erro JSON
            dados_serializados = serializar_dados_dinamicos(dados_dinamicos)
            cliente_obj.dados_dinamicos = dados_serializados
            print(f"   💾 Salvando {len(dados_dinamicos)} dados dinâmicos dos templates SQL:")
            for chave, valor in dados_dinamicos.items():
                print(f"      📝 {chave}: {valor}")
        else:
            print("   ℹ️  Nenhum dado dinâmico encontrado nos templates SQL")
        
        cliente_obj.save()
        
        print("✅ Cliente salvo com sucesso")
        print("-"*80)
        print("📋 RESUMO DOS DADOS ATUALIZADOS:")
        print(f"   �� Nome: {cliente_obj.nome_razaosocial}")
        print(f"   �� Telefone: {cliente_obj.telefone_corrigido}")
        print(f"   🏷️  ID Fatura: {cliente_obj.id_fatura}")
        print(f"   �� Valor: R$ {cliente_obj.valor_fatura}")
        print(f"   📅 Vencimento: {cliente_obj.vencimento_fatura}")
        print(f"   💳 PIX: {'Sim' if cliente_obj.pix else 'Não'}: {cliente_obj.pix}")
        print(f"   📊 Código de Barras: {'Sim' if cliente_obj.codigo_barras else 'Não'}: {cliente_obj.codigo_barras}")
        print(f"   �� Link Boleto: {'Sim' if cliente_obj.link_boleto else 'Não'}: {cliente_obj.link_boleto}")
        print(f"   ⏰ Última Atualização: {cliente_obj.data_atualizacao}")
        print("-"*80)
        
        # Registra a consulta
        print("�� REGISTRANDO CONSULTA...")
        
        # Define sucesso da API baseado na configuração
        sucesso_api = execucao.pular_consulta_api or (dados_cliente is not None)
        
        consulta_cliente, created = ConsultaCliente.objects.get_or_create(
            execucao=execucao,
            cliente=cliente_obj,
            defaults={
                'dados_originais_sql': cliente_data,
                'dados_api_response': dados_cliente,
                'sucesso_api': sucesso_api,
                'erro_api': None if execucao.pular_consulta_api else None
            }
        )
        
        # Se já existia, atualiza os dados
        if not created:
            consulta_cliente.dados_originais_sql = cliente_data
            consulta_cliente.dados_api_response = dados_cliente
            consulta_cliente.sucesso_api = sucesso_api
            consulta_cliente.erro_api = None if execucao.pular_consulta_api else None
            consulta_cliente.save()
            print("✅ Consulta existente atualizada")
            logger.info(f"Atualizando consulta existente para cliente {codigo_cliente}")
        else:
            print("✅ Nova consulta registrada")
            
        if execucao.pular_consulta_api:
            print("ℹ️  API não foi consultada conforme configuração da execução")
        
        print("🎉 PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        print("="*80)
        
        return cliente_obj, None
        
    except Exception as e:
        # Se ainda não temos error_msg, captura o erro atual
        if not error_msg:
            error_msg = f"Erro ao processar cliente {codigo_cliente}: {str(e)}"
        
        # Se a API foi pulada, não considera como erro de API
        if execucao.pular_consulta_api and "API" in error_msg:
            print(f"ℹ️  Erro relacionado à API ignorado (API foi pulada): {error_msg}")
            # Tenta processar apenas com dados SQL
            try:
                print("🔄 TENTANDO PROCESSAR APENAS COM DADOS SQL...")
                
                # Garante que o cliente existe
                cliente_obj, created = ClienteConsultado.objects.get_or_create(
                    codigo_cliente=codigo_cliente,
                    credencial_banco=execucao.credencial_banco,
                    defaults={
                        'nome_razaosocial': normalizar_texto(cliente_data.get('nome_razaosocial', '')),
                        'telefone_corrigido': cliente_data.get('TelefoneCorrigido', '') or cliente_data.get('telefonecorrigido', ''),
                        'id_fatura': id_fatura_desejada,
                        # CORRIGIDO: Adiciona todos os campos que podem vir do SQL
                        'valor_fatura': cliente_data.get('valor', ''),
                        'vencimento_fatura': cliente_data.get('data_vencimento', ''),
                        'pix': cliente_data.get('pix_copia_cola', ''),
                        'codigo_barras': cliente_data.get('linha_digitavel', ''),
                        'link_boleto': cliente_data.get('link', ''),
                        'data_criacao': timezone.now()
                    }
                )
                
                # Se cliente já existia, atualiza os campos do SQL
                if not created:
                    print("🔄 Cliente já existe, atualizando campos do SQL...")
                    cliente_obj.valor_fatura = cliente_data.get('valor', '') or cliente_obj.valor_fatura
                    cliente_obj.vencimento_fatura = cliente_data.get('data_vencimento', '') or cliente_obj.vencimento_fatura
                    cliente_obj.pix = cliente_data.get('pix_copia_cola', '') or cliente_obj.pix
                    cliente_obj.codigo_barras = cliente_data.get('linha_digitavel', '') or cliente_obj.codigo_barras
                    cliente_obj.link_boleto = cliente_data.get('link', '') or cliente_obj.link_boleto
                
                # Processa dados dinâmicos
                from .utils import extrair_dados_dinamicos_sql
                dados_dinamicos = extrair_dados_dinamicos_sql(cliente_data, None)
                if dados_dinamicos:
                    # Serializar dados dinâmicos para evitar erro JSON
                    dados_serializados = serializar_dados_dinamicos(dados_dinamicos)
                    cliente_obj.dados_dinamicos = dados_serializados
                
                cliente_obj.save()
                
                # Registra como sucesso (apenas SQL)
                consulta_cliente, created = ConsultaCliente.objects.get_or_create(
                    execucao=execucao,
                    cliente=cliente_obj,
                    defaults={
                        'dados_originais_sql': cliente_data,
                        'dados_api_response': None,
                        'sucesso_api': True,  # Sucesso porque API foi pulada intencionalmente
                        'erro_api': None
                    }
                )
                
                print("✅ Cliente processado com sucesso (apenas dados SQL)")
                return cliente_obj, None
                
            except Exception as sql_error:
                error_msg = f"Erro ao processar dados SQL: {str(sql_error)}"
        
        print(f"❌ ERRO NO PROCESSAMENTO: {error_msg}")
        logger.error(error_msg)
        
        # SEMPRE registra o erro, mesmo que o cliente não exista ainda
        try:
            print("🔄 REGISTRANDO ERRO...")
            
            # Garante que o cliente existe para poder registrar o erro
            if not cliente_obj and codigo_cliente:
                cliente_obj, _ = ClienteConsultado.objects.get_or_create(
                    codigo_cliente=codigo_cliente,
                    defaults={
                        'nome_razaosocial': normalizar_texto(cliente_data.get('nome_razaosocial', '')) or 'Nome não disponível',
                        'telefone_corrigido': cliente_data.get('TelefoneCorrigido', '') or cliente_data.get('telefonecorrigido', ''),
                        'id_fatura': id_fatura_desejada,
                        'data_criacao': timezone.now()
                    }
                )
                print(f"✅ Cliente criado para registro de erro: {cliente_obj.codigo_cliente}")
            
            # Registra a consulta com erro
            if cliente_obj:
                consulta_cliente, created = ConsultaCliente.objects.get_or_create(
                    execucao=execucao,
                    cliente=cliente_obj,
                    defaults={
                        'dados_originais_sql': cliente_data,
                        'sucesso_api': False,
                        'erro_api': error_msg,
                        'dados_api_response': None
                    }
                )
                
                # Se já existia, atualiza os dados do erro
                if not created:
                    consulta_cliente.dados_originais_sql = cliente_data
                    consulta_cliente.sucesso_api = False
                    consulta_cliente.erro_api = error_msg
                    consulta_cliente.dados_api_response = None
                    consulta_cliente.save()
                    print("✅ Erro atualizado em consulta existente")
                    logger.info(f"Atualizando erro da consulta existente para cliente {codigo_cliente}")
                else:
                    print("✅ Novo erro registrado")
                    logger.info(f"Registrado erro para cliente {codigo_cliente}: {error_msg}")
        
        except Exception as registro_erro:
            print(f"❌ ERRO AO REGISTRAR ERRO: {str(registro_erro)}")
            logger.error(f"Erro ao registrar erro do cliente {codigo_cliente}: {str(registro_erro)}")
        
        print("💥 PROCESSAMENTO FINALIZADO COM ERRO!")
        print("="*80)
        
        return None, error_msg

def processar_consulta_completa(execucao_id):
    """Função que executa todo o processamento em background"""
    try:
        execucao = ConsultaExecucao.objects.get(id=execucao_id)
        execucao.atualizar_status('executando', 'Iniciando processamento...')
        
        # 1. Executar consulta SQL
        logger.info(f"Executando consulta SQL para execução {execucao_id}")
        resultados_sql = executar_consulta_sql(
            execucao.credencial_banco, 
            execucao.template_sql,
            execucao.valores_variaveis
        )
        
        execucao.total_registros_sql = len(resultados_sql)
        execucao.save()
        
        if not resultados_sql:
            execucao.atualizar_status('erro', 'Nenhum resultado encontrado na consulta SQL')
            return
        
        # Verifica duplicatas nos resultados SQL
        codigos_clientes = [row.get('codigo_cliente') for row in resultados_sql if row.get('codigo_cliente')]
        codigos_unicos = set(codigos_clientes)
        if len(codigos_clientes) != len(codigos_unicos):
            duplicatas = len(codigos_clientes) - len(codigos_unicos)
            logger.warning(f"Encontradas {duplicatas} duplicatas nos resultados SQL")
            log_buffer = StringIO()
            log_buffer.write(f"⚠️ AVISO: Encontradas {duplicatas} duplicatas nos resultados SQL\n")
            log_buffer.write(f"Total de registros: {len(codigos_clientes)}, Clientes únicos: {len(codigos_unicos)}\n\n")
        else:
            log_buffer = StringIO()
        
        # 2. Inicializar cliente da API
        api_client = HubsoftAPI(execucao.credencial_hubsoft)
        
        # 3. Processar cada cliente
        total_processados = 0
        total_erros = 0
        
        for i, cliente_data in enumerate(resultados_sql, 1):
            # Verifica se a execução foi cancelada
            execucao.refresh_from_db()
            if execucao.status == 'cancelada':
                logger.info(f"Processamento da execução {execucao_id} foi cancelado pelo usuário")
                return
            
            log_buffer.write(f"Processando {i}/{len(resultados_sql)}: {cliente_data.get('codigo_cliente')}\n")
            
            cliente_obj, erro = processar_cliente_api(api_client, cliente_data, execucao)
            
            if cliente_obj:
                total_processados += 1
                log_buffer.write(f"✓ Sucesso: Cliente {cliente_data.get('codigo_cliente')}\n")
            else:
                total_erros += 1
                log_buffer.write(f"✗ Erro: {erro}\n")
            
            # Delay entre requisições
            time.sleep(0.5)
            
            # Atualiza progresso a cada 10 registros
            if i % 10 == 0:
                execucao.total_consultados_api = total_processados
                execucao.total_erros = total_erros
                execucao.log_execucao = log_buffer.getvalue()
                execucao.save()
        
        # Finalizar execução
        execucao.total_consultados_api = total_processados
        execucao.total_erros = total_erros
        execucao.log_execucao = log_buffer.getvalue()
        execucao.atualizar_status('concluida', f'Processamento concluído. {total_processados} sucessos, {total_erros} erros.')
        
        logger.info(f"Processamento da execução {execucao_id} finalizado")
        
    except Exception as e:
        logger.error(f"Erro no processamento da execução {execucao_id}: {e}")
        try:
            execucao = ConsultaExecucao.objects.get(id=execucao_id)
            execucao.atualizar_status('erro', f'Erro durante processamento: {str(e)}')
        except:
            pass

@require_http_methods(["POST"])
def iniciar_processamento(request):
    """Inicia o processamento de uma nova consulta (AJAX-aware)"""
    try:
        titulo = request.POST.get('titulo')
        template_id = request.POST.get('template_sql')
        hubsoft_id = request.POST.get('credencial_hubsoft')
        banco_id = request.POST.get('credencial_banco')
        pular_consulta_api = request.POST.get('pular_consulta_api') == 'on'  # Checkbox value

        # Validação básica
        if not all([titulo, template_id, banco_id]):
            return JsonResponse({
                'status': 'error',
                'message': 'Título, Template SQL e Credencial de Banco são obrigatórios.'
            }, status=400)
        
        # Validação condicional da credencial Hubsoft
        if not pular_consulta_api and not hubsoft_id:
            return JsonResponse({
                'status': 'error',
                'message': 'Credencial Hubsoft é obrigatória quando a consulta da API está habilitada.'
            }, status=400)

        # Capturar valores das variáveis
        template_sql = TemplateSQL.objects.get(id=template_id)
        variaveis_config = template_sql.get_variaveis_configuradas()
        valores_variaveis = {}
        
        # Validar e capturar cada variável
        for var_name, config in variaveis_config.items():
            valor = request.POST.get(f'var_{var_name}')
            
            if config.get('obrigatorio', True) and not valor:
                return JsonResponse({
                    'status': 'error',
                    'message': f'A variável "{config.get("label", var_name)}" é obrigatória.'
                }, status=400)
            
            # Usar valor padrão se não fornecido e não obrigatório
            if not valor and not config.get('obrigatorio', True):
                valor = config.get('valor_padrao', '')
            
            valores_variaveis[var_name] = valor

        # Criar nova execução
        execucao = ConsultaExecucao.objects.create(
            titulo=titulo,
            template_sql_id=template_id,
            credencial_hubsoft_id=hubsoft_id if not pular_consulta_api else None,
            credencial_banco_id=banco_id,
            valores_variaveis=valores_variaveis,
            pular_consulta_api=pular_consulta_api,
            status='pendente'
        )

        # Iniciar processamento em thread separada
        thread = threading.Thread(target=processar_consulta_completa, args=(execucao.id,))
        thread.daemon = True
        thread.start()
        
        # --- MUDANÇA 2: Resposta de sucesso retorna JSON com URL de redirect ---
        # Gera a URL para a página de detalhes da execução
        redirect_url = reverse('detalhe_execucao', args=[execucao.id])

        return JsonResponse({
            'status': 'success',
            'message': f'Processamento "{execucao.titulo}" iniciado com sucesso!',
            'redirect_url': redirect_url # Informa ao frontend para onde ir
        })

    except Exception as e:
        logger.error(f"Erro ao iniciar processamento: {e}")
        # --- MUDANÇA 3: Exceção geral retorna JSON de erro ---
        # Retorna um erro 500 (Internal Server Error) com uma mensagem JSON
        return JsonResponse({
            'status': 'error',
            'message': f'Ocorreu um erro interno no servidor: {str(e)}'
        }, status=500)
    
def listar_execucoes(request):
    """Lista todas as execuções"""
    execucoes = ConsultaExecucao.objects.all().order_by('-data_inicio')
    paginator = Paginator(execucoes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'campanhas/listar_execucoes.html', {'page_obj': page_obj})

def detalhe_execucao(request, execucao_id):
    """Mostra detalhes de uma execução específica"""
    execucao = get_object_or_404(ConsultaExecucao, id=execucao_id)
    consultas_clientes = ConsultaCliente.objects.filter(execucao=execucao).order_by('-data_consulta')
    
    # Paginação das consultas
    paginator = Paginator(consultas_clientes, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Busca informações do último envio HSM (se existir)
    ultimo_envio_hsm = None
    if execucao.status == 'concluida':
        ultimo_envio_hsm = EnvioHSMMatrix.objects.filter(
            consulta_execucao=execucao
        ).order_by('-data_criacao').first()
    
    # NOVO: Analisa variáveis dinâmicas disponíveis na execução
    variaveis_dinamicas_info = analisar_variaveis_dinamicas_execucao(execucao)
    
    context = {
        'execucao': execucao,
        'page_obj': page_obj,
        'total_consultas': consultas_clientes.count(),
        'ultimo_envio_hsm': ultimo_envio_hsm,
        'variaveis_dinamicas_info': variaveis_dinamicas_info
    }
    
    return render(request, 'campanhas/detalhe_execucao.html', context)

def status_execucao_ajax(request, execucao_id):
    """Retorna o status atual de uma execução via AJAX"""
    try:
        execucao = ConsultaExecucao.objects.get(id=execucao_id)
        return JsonResponse({
            'status': execucao.status,
            'total_registros_sql': execucao.total_registros_sql,
            'total_consultados_api': execucao.total_consultados_api,
            'total_erros': execucao.total_erros,
            'log_execucao': execucao.log_execucao or '',
            'data_fim': execucao.data_fim.isoformat() if execucao.data_fim else None
        })
    except ConsultaExecucao.DoesNotExist:
        return JsonResponse({'error': 'Execução não encontrada'}, status=404)

def exportar_resultados_csv(request, execucao_id):
    """Exporta os resultados de uma execução para CSV"""
    execucao = get_object_or_404(ConsultaExecucao, id=execucao_id)
    
    # Verifica se deve incluir erros
    incluir_erros = request.GET.get('incluir_erros', 'false').lower() == 'true'
    
    if incluir_erros:
        # Exporta todos os registros (sucessos e erros)
        consultas = ConsultaCliente.objects.filter(execucao=execucao)
        filename_suffix = "completo"
    else:
        # Exporta registros válidos considerando se a API foi pulada
        if execucao.pular_consulta_api:
            # Se API foi pulada, exporta todos os clientes processados
            consultas = ConsultaCliente.objects.filter(execucao=execucao)
            filename_suffix = "processados"
        else:
            # Se API foi consultada, exporta apenas sucessos
            consultas = ConsultaCliente.objects.filter(execucao=execucao, sucesso_api=True)
            filename_suffix = "sucessos"
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="resultados_{filename_suffix}_{execucao.titulo}_{execucao.id}.csv"'
    
    # Criar DataFrame com os resultados
    dados = []
    for consulta in consultas:
        cliente = consulta.cliente
        # Base comum (campos não dinâmicos)
        linha = {
            'Status': 'Sucesso' if consulta.sucesso_api else 'Erro',
            'Codigo_Cliente': cliente.codigo_cliente,
            'Telefone': cliente.telefone_corrigido or '',
            'Nome': cliente.nome_razaosocial,
            'ID_Fatura': cliente.id_fatura or '',
            'Valor_Fatura': cliente.valor_fatura or '',
            'Data_Vencimento': cliente.vencimento_fatura or '',
            'Codigo_Barras': cliente.codigo_barras or '',
            'PIX_Copia_Cola': cliente.pix or '',
            'Link_Boleto': cliente.link_boleto or '',
            'Empresa': cliente.credencial_banco.titulo if getattr(cliente, 'credencial_banco', None) else '',
            'Erro': '' if consulta.sucesso_api else (consulta.erro_api or 'Erro não especificado'),
            'Data_Consulta': consulta.data_consulta.strftime('%d/%m/%Y %H:%M:%S')
        }
        # Adiciona variáveis dinâmicas (exceto 'faturas')
        try:
            dados_dinamicos = cliente.get_todos_dados_dinamicos()
        except Exception:
            dados_dinamicos = getattr(cliente, 'dados_dinamicos', {}) or {}
        for chave, valor in (dados_dinamicos or {}).items():
            if isinstance(chave, str) and chave.lower() == 'faturas':
                continue
            linha[chave] = valor
        dados.append(linha)
    
    if dados:
        df = pd.DataFrame(dados)
        df.to_csv(response, index=False, encoding='utf-8')
    
    return response

def exportar_erros_csv(request, execucao_id):
    """Exporta apenas os erros de uma execução para CSV"""
    execucao = get_object_or_404(ConsultaExecucao, id=execucao_id)
    consultas_erro = ConsultaCliente.objects.filter(execucao=execucao, sucesso_api=False)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="erros_{execucao.titulo}_{execucao.id}.csv"'
    
    # Criar DataFrame com os erros
    dados = []
    for consulta in consultas_erro:
        cliente = consulta.cliente
        linha = {
            'Codigo_Cliente': cliente.codigo_cliente,
            'Nome': cliente.nome_razaosocial,
            'Telefone': cliente.telefone_corrigido or '',
            'ID_Fatura': cliente.id_fatura or '',
            'Valor_Fatura': cliente.valor_fatura or '',
            'Data_Vencimento': cliente.vencimento_fatura or '',
            'Codigo_Barras': cliente.codigo_barras or '',
            'PIX_Copia_Cola': cliente.pix or '',
            'Link_Boleto': cliente.link_boleto or '',
            'Empresa': cliente.credencial_banco.titulo if getattr(cliente, 'credencial_banco', None) else '',
            'Erro': consulta.erro_api or 'Erro não especificado',
            'Data_Consulta': consulta.data_consulta.strftime('%d/%m/%Y %H:%M:%S'),
            'Dados_SQL_Originais': str(consulta.dados_originais_sql) if consulta.dados_originais_sql else ''
        }
        # Adiciona variáveis dinâmicas (exceto 'faturas')
        try:
            dados_dinamicos = cliente.get_todos_dados_dinamicos()
        except Exception:
            dados_dinamicos = getattr(cliente, 'dados_dinamicos', {}) or {}
        for chave, valor in (dados_dinamicos or {}).items():
            if isinstance(chave, str) and chave.lower() == 'faturas':
                continue
            linha[chave] = valor
        dados.append(linha)
    
    if dados:
        df = pd.DataFrame(dados)
        df.to_csv(response, index=False, encoding='utf-8')
    
    return response

@require_http_methods(["POST"])
def cancelar_processamento(request, execucao_id):
    """Cancela uma execução em andamento"""
    try:
        execucao = ConsultaExecucao.objects.get(id=execucao_id)
        
        if execucao.status not in ['pendente', 'executando']:
            return JsonResponse({
                'status': 'error',
                'message': 'Apenas execuções pendentes ou em andamento podem ser canceladas.'
            }, status=400)
        
        # Atualiza o log para indicar o cancelamento
        log_atual = execucao.log_execucao or ''
        timestamp = timezone.now().strftime('%d/%m/%Y %H:%M:%S')
        log_cancelamento = f"\n[{timestamp}] ⚠️ PROCESSAMENTO CANCELADO PELO USUÁRIO\n"
        
        execucao.status = 'cancelada'
        execucao.data_fim = timezone.now()
        execucao.erro = 'Processamento cancelado pelo usuário.'
        execucao.log_execucao = log_atual + log_cancelamento
        execucao.save()
        
        logger.info(f"Execução {execucao_id} cancelada pelo usuário")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Processamento cancelado com sucesso.'
        })
        
    except ConsultaExecucao.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Execução não encontrada.'
        }, status=404)
    except Exception as e:
        logger.error(f"Erro ao cancelar execução {execucao_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao cancelar processamento: {str(e)}'
        }, status=500)

@require_http_methods(["POST"])
def reiniciar_processamento(request, execucao_id):
    """Reinicia uma execução finalizada resetando seus dados"""
    try:
        execucao = ConsultaExecucao.objects.get(id=execucao_id)
        
        if execucao.status not in ['concluida', 'erro', 'cancelada']:
            return JsonResponse({
                'status': 'error',
                'message': 'Apenas execuções finalizadas podem ser reiniciadas.'
            }, status=400)
        
        # Remove todas as consultas de clientes relacionadas a esta execução
        ConsultaCliente.objects.filter(execucao=execucao).delete()
        
        # Reseta os dados da execução para o estado inicial
        execucao.status = 'pendente'
        execucao.data_fim = None
        execucao.erro = None
        execucao.total_registros_sql = 0
        execucao.total_consultados_api = 0
        execucao.total_erros = 0
        execucao.log_execucao = ''
        execucao.data_inicio = timezone.now()  # Atualiza para o momento do reinício
        execucao.save()
        
        # Inicia o processamento em thread separada
        thread = threading.Thread(target=processar_consulta_completa, args=(execucao.id,))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Execução {execucao_id} reiniciada (dados resetados)")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Processamento reiniciado com sucesso.',
            'redirect_url': reverse('detalhe_execucao', args=[execucao.id])
        })
        
    except ConsultaExecucao.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Execução não encontrada.'
        }, status=404)
    except Exception as e:
        logger.error(f"Erro ao reiniciar execução {execucao_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao reiniciar processamento: {str(e)}'
        }, status=500)

def detalhes_cliente(request, cliente_id):
    """Exibe todos os detalhes de um cliente processado"""
    try:
        cliente = ClienteConsultado.objects.get(id=cliente_id)
        consultas = ConsultaCliente.objects.filter(cliente=cliente).select_related('execucao').order_by('-data_consulta')
        
        # Prepara os dados do cliente para exibição
        dados_cliente = {
            'codigo_cliente': cliente.codigo_cliente,
            'nome_razaosocial': cliente.nome_razaosocial,
            'telefone_corrigido': cliente.telefone_corrigido,
            'id_fatura': cliente.id_fatura,
            'vencimento_fatura': cliente.vencimento_fatura,
            'valor_fatura': cliente.valor_fatura,
            'pix': cliente.pix,
            'codigo_barras': cliente.codigo_barras,
            'link_boleto': cliente.link_boleto,
            'data_criacao': cliente.data_criacao,
            'data_atualizacao': cliente.data_atualizacao
        }
        
        context = {
            'cliente': cliente,
            'dados_cliente': dados_cliente,
            'consultas': consultas,
        }
        
        return render(request, 'campanhas/detalhes_cliente.html', context)
        
    except ClienteConsultado.DoesNotExist:
        messages.error(request, 'Cliente não encontrado')
        return redirect('listar_execucoes')

# =============================================================================
# VIEWS PARA ENVIO HSM VIA MATRIX
# =============================================================================

def configurar_envio_hsm(request, execucao_id):
    """Página para configurar o envio de HSM para uma execução"""
    execucao = get_object_or_404(ConsultaExecucao, id=execucao_id)
    
    # Verifica se a execução foi concluída com sucesso
    if execucao.status != 'concluida':
        messages.error(request, 'Apenas execuções concluídas podem ter HSM enviado.')
        return redirect('detalhe_execucao', execucao_id=execucao_id)
    
    # Busca clientes válidos considerando se a API foi pulada
    if execucao.pular_consulta_api:
        # Se API foi pulada, considera todos os clientes da execução como válidos
        clientes_sucesso = ConsultaCliente.objects.filter(
            execucao=execucao
        ).count()
        print(f"🔄 API foi pulada: considerando {clientes_sucesso} clientes para envio")
    else:
        # Se API foi consultada, considera apenas sucessos
        clientes_sucesso = ConsultaCliente.objects.filter(
            execucao=execucao, 
            sucesso_api=True
        ).count()
        print(f"📡 API foi consultada: {clientes_sucesso} clientes com sucesso")
    
    if clientes_sucesso == 0:
        if execucao.pular_consulta_api:
            messages.error(request, 'Nenhum cliente foi processado nesta execução.')
        else:
            messages.error(request, 'Nenhum cliente com dados válidos encontrado nesta execução.')
        return redirect('detalhe_execucao', execucao_id=execucao_id)
    
    # Busca configurações e templates disponíveis
    matrix_configs = MatrixAPIConfig.objects.filter(ativo=True)
    hsm_templates_padrao = HSMTemplate.objects.filter(ativo=True, tipo_template='padrao')
    hsm_templates_pagamento = HSMTemplate.objects.filter(ativo=True, tipo_template='pagamento')
    hsm_templates = HSMTemplate.objects.filter(ativo=True)  # Todos os templates para compatibilidade
    configuracoes_pagamento = ConfiguracaoPagamentoHSM.objects.filter(ativo=True)
    
    # Busca último envio para reutilizar configurações
    ultimo_envio = obter_ultimo_envio_hsm(execucao_id)
    
    # NOVO: Analisa variáveis dinâmicas disponíveis na execução
    variaveis_dinamicas_info = analisar_variaveis_dinamicas_execucao(execucao)
    
    context = {
        'execucao': execucao,
        'clientes_sucesso': clientes_sucesso,
        'matrix_configs': matrix_configs,
        'hsm_templates': hsm_templates,  # Lista completa para compatibilidade
        'hsm_templates_padrao': hsm_templates_padrao,
        'hsm_templates_pagamento': hsm_templates_pagamento,
        'configuracoes_pagamento': configuracoes_pagamento,
        'ultimo_envio': ultimo_envio,
        'variaveis_dinamicas_info': variaveis_dinamicas_info
    }
    
    return render(request, 'campanhas/configurar_envio_hsm.html', context)

def obter_variaveis_hsm_template(request, template_id):
    """Retorna as variáveis de um template HSM específico via AJAX"""
    try:
        template = HSMTemplate.objects.get(id=template_id, ativo=True)
        variaveis = template.get_variaveis_descricao()
        
        return JsonResponse({
            'status': 'success',
            'variaveis': variaveis,
            'template_nome': template.nome,
            'hsm_id': template.hsm_id,
            'cod_flow': template.cod_flow,
            'tipo_envio': template.tipo_envio
        })
    except HSMTemplate.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Template HSM não encontrado'
        }, status=404)
    except Exception as e:
        logger.error(f"Erro ao obter variáveis do template HSM {template_id}: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=500)

def serializar_valor_para_json(valor):
    """Converte valores para tipos serializáveis em JSON com tratamento especial para strings"""
    if valor is None:
        return ''
    
    # Se é um objeto date ou datetime, converte para string
    if hasattr(valor, 'strftime'):
        if hasattr(valor, 'hour'):  # datetime
            return valor.strftime('%d/%m/%Y %H:%M')
        else:  # date
            return valor.strftime('%d/%m/%Y')
    
    # ✅ CORREÇÃO: Tratamento especial para strings com espaços
    if isinstance(valor, str):
        # Remove espaços extras e normaliza
        valor_limpo = ' '.join(valor.strip().split())
        # Garante encoding UTF-8 correto
        return valor_limpo.encode('utf-8').decode('utf-8')
    
    # Converte outros tipos para string com tratamento de encoding
    valor_str = str(valor) if valor else ''
    if valor_str:
        # Garante encoding UTF-8 correto para todos os valores
        return valor_str.encode('utf-8').decode('utf-8')
    
    return ''

def safe_decimal_to_float(decimal_value, default=0.0):
    """Converte um campo Decimal para float de forma segura"""
    if decimal_value is None:
        return default
    try:
        return float(decimal_value) if decimal_value > 0 else default
    except (ValueError, TypeError):
        return default

def mapear_campos_cliente_para_hsm(cliente_data):
    """
    Mapeia os campos do cliente para variáveis do HSM incluindo TODAS as variáveis dinâmicas
    
    Args:
        cliente_data: Dict com dados do cliente OU objeto ClienteConsultado
    
    Returns:
        dict: Mapeamento completo para HSM (campos fixos + dinâmicos)
    """
    
    # Se receber um objeto Cliente, converte para dict completo
    if hasattr(cliente_data, 'get_dados_completos'):
        print("   🔄 Usando dados completos do objeto Cliente (inclui dinâmicos)")
        dados_completos = cliente_data.get_dados_completos()
        print(f"   📊 Dados completos obtidos: {len(dados_completos)} campos")
        print(f"   📝 Campos disponíveis: {list(dados_completos.keys())}")
        
        # Verifica especificamente os dados dinâmicos
        dados_dinamicos = cliente_data.get_todos_dados_dinamicos()
        print(f"   🎯 Dados dinâmicos específicos: {dados_dinamicos}")
    else:
        print("   📋 Usando dados fornecidos como dict")
        dados_completos = cliente_data
        print(f"   📊 Dict fornecido: {len(dados_completos)} campos")
        print(f"   📝 Campos no dict: {list(dados_completos.keys())}")
    
    # ✅ CORREÇÃO CRÍTICA: Mapeamento usando nomes dos campos originais como chaves
    # Isso garante que o processamento background encontre os valores corretos
    mapeamento = {
        # Campos com nomes originais (para compatibilidade com configuracao_variaveis)
        'nome_razaosocial': serializar_valor_para_json(dados_completos.get('nome_razaosocial')),
        'codigo_cliente': serializar_valor_para_json(dados_completos.get('codigo_cliente')),
        'telefone_corrigido': serializar_valor_para_json(dados_completos.get('telefone_corrigido')),
        'valor_fatura': serializar_valor_para_json(dados_completos.get('valor_fatura')),
        'vencimento_fatura': serializar_valor_para_json(dados_completos.get('vencimento_fatura')),
        'codigo_barras': serializar_valor_para_json(dados_completos.get('codigo_barras')),
        'pix': serializar_valor_para_json(dados_completos.get('pix')),
        'link_boleto': serializar_valor_para_json(dados_completos.get('link_boleto')),
        'id_fatura': serializar_valor_para_json(dados_completos.get('id_fatura')),
        'empresa': serializar_valor_para_json(dados_completos.get('empresa')),
        
        # Campos com nomes alternativos (para compatibilidade com templates antigos)
        'nome_cliente': serializar_valor_para_json(dados_completos.get('nome_razaosocial')),
        'telefone': serializar_valor_para_json(dados_completos.get('telefone_corrigido')),
        'pix_copia_cola': serializar_valor_para_json(dados_completos.get('pix'))
    }
    
    # Identifica campos fixos do modelo ClienteConsultado (para não duplicar como dinâmicos)
    campos_fixos = {
        'codigo_cliente', 'nome_razaosocial', 'telefone_corrigido', 
        'id_fatura', 'vencimento_fatura', 'valor_fatura', 'pix', 
        'codigo_barras', 'link_boleto', 'dados_dinamicos', 'credencial_banco',
        'empresa', 'data_criacao', 'data_atualizacao'
    }
    
    # NOVO: Adiciona TODAS as variáveis dinâmicas (campos não-fixos)
    variaveis_dinamicas = 0
    print(f"   🔍 Verificando campos dinâmicos entre {len(dados_completos)} campos disponíveis...")
    print(f"   🚫 Campos fixos (ignorados): {campos_fixos}")
    
    for chave, valor in dados_completos.items():
        if chave not in campos_fixos and valor is not None and valor != '':
            # Adiciona com prefixo para identificação clara
            nome_variavel = f"dinamico_{chave}"
            valor_serializado = serializar_valor_para_json(valor)
            mapeamento[nome_variavel] = valor_serializado
            
            # Também adiciona sem prefixo para compatibilidade
            mapeamento[chave] = valor_serializado
            
            print(f"   ✅ Adicionado: {chave} = '{valor}' (também como dinamico_{chave})")
            variaveis_dinamicas += 1
        elif chave not in campos_fixos:
            print(f"   ⚠️  Ignorado (vazio/nulo): {chave} = '{valor}'")
    
    if variaveis_dinamicas > 0:
        print(f"   📝 Total de {variaveis_dinamicas} variáveis dinâmicas adicionadas ao HSM")
    else:
        print(f"   ❌ Nenhuma variável dinâmica encontrada para adicionar ao HSM")
    
    # Adiciona metadados úteis
    mapeamento.update({
        'total_variaveis_dinamicas': variaveis_dinamicas,
        'data_ultima_atualizacao': serializar_valor_para_json(dados_completos.get('data_atualizacao')),
        'source': 'sistema_campanhas'
    })
    
    print(f"   🎯 Total de variáveis disponíveis para HSM: {len(mapeamento)}")
    
    return mapeamento

def listar_variaveis_disponiveis_cliente(cliente):
    """
    Lista todas as variáveis disponíveis de um cliente para uso em HSM e Flow
    
    Args:
        cliente: Objeto ClienteConsultado ou dict com dados
    
    Returns:
        dict: Lista organizada de variáveis com descrições
    """
    if hasattr(cliente, 'get_dados_completos'):
        dados_completos = cliente.get_dados_completos()
        dados_dinamicos = cliente.get_todos_dados_dinamicos()
    else:
        dados_completos = cliente
        dados_dinamicos = cliente.get('dados_dinamicos', {})
    
    variaveis = {
        'campos_fixos': {
            'nome_cliente': {
                'valor': dados_completos.get('nome_razaosocial', ''),
                'descricao': 'Nome ou razão social do cliente',
                'tipo': 'texto'
            },
            'codigo_cliente': {
                'valor': dados_completos.get('codigo_cliente', ''),
                'descricao': 'Código único do cliente',
                'tipo': 'texto'
            },
            'telefone': {
                'valor': dados_completos.get('telefone_corrigido', ''),
                'descricao': 'Telefone do cliente',
                'tipo': 'telefone'
            },
            'valor_fatura': {
                'valor': dados_completos.get('valor_fatura', ''),
                'descricao': 'Valor da fatura',
                'tipo': 'moeda'
            },
            'vencimento_fatura': {
                'valor': dados_completos.get('vencimento_fatura', ''),
                'descricao': 'Data de vencimento da fatura',
                'tipo': 'data'
            },
            'codigo_barras': {
                'valor': dados_completos.get('codigo_barras', ''),
                'descricao': 'Código de barras do boleto',
                'tipo': 'codigo'
            },
            'pix_copia_cola': {
                'valor': dados_completos.get('pix', ''),
                'descricao': 'Código PIX para pagamento',
                'tipo': 'codigo'
            },
            'link_boleto': {
                'valor': dados_completos.get('link_boleto', ''),
                'descricao': 'Link para visualizar o boleto',
                'tipo': 'url'
            },
            'id_fatura': {
                'valor': dados_completos.get('id_fatura', ''),
                'descricao': 'ID da fatura',
                'tipo': 'texto'
            },
            'empresa': {
                'valor': dados_completos.get('empresa', ''),
                'descricao': 'Nome da empresa/base de dados',
                'tipo': 'texto'
            }
        },
        'campos_dinamicos': {},
        'metadados': {
            'total_variaveis_dinamicas': {
                'valor': len(dados_dinamicos),
                'descricao': 'Quantidade de variáveis dinâmicas',
                'tipo': 'numero'
            },
            'data_ultima_atualizacao': {
                'valor': dados_completos.get('data_atualizacao', ''),
                'descricao': 'Data da última atualização',
                'tipo': 'data'
            }
        }
    }
    
    # Adiciona campos dinâmicos
    for chave, valor in dados_dinamicos.items():
        variaveis['campos_dinamicos'][chave] = {
            'valor': valor,
            'descricao': f'Dado dinâmico: {chave}',
            'tipo': 'dinamico',
            'nome_hsm': f'dinamico_{chave}',  # Nome com prefixo para HSM
            'nome_flow': chave  # Nome direto para Flow
        }
    
    return variaveis

def analisar_variaveis_dinamicas_execucao(execucao):
    """
    Analisa todas as variáveis dinâmicas disponíveis em uma execução
    
    Args:
        execucao: Objeto ConsultaExecucao
    
    Returns:
        dict: Informações completas sobre variáveis dinâmicas da execução
    """
    # Busca alguns clientes com dados para análise
    clientes_com_dados = ClienteConsultado.objects.filter(
        consultacliente__execucao=execucao
    ).exclude(dados_dinamicos={}).distinct()[:10]  # Pega até 10 clientes para amostra
    
    # Coleta todas as variáveis dinâmicas únicas
    todas_variaveis_dinamicas = set()
    exemplos_variaveis = {}
    
    for cliente in clientes_com_dados:
        dados_dinamicos = cliente.get_todos_dados_dinamicos()
        for chave, valor in dados_dinamicos.items():
            todas_variaveis_dinamicas.add(chave)
            if chave not in exemplos_variaveis:
                exemplos_variaveis[chave] = {
                    'valor_exemplo': valor,
                    'cliente_exemplo': cliente.nome_razaosocial,
                    'tipo': type(valor).__name__
                }
    
    # Estatísticas
    total_clientes_execucao = ClienteConsultado.objects.filter(
        consultacliente__execucao=execucao
    ).count()
    
    clientes_com_dinamicos = ClienteConsultado.objects.filter(
        consultacliente__execucao=execucao
    ).exclude(dados_dinamicos={}).count()
    
    # Analisa o template SQL para ver campos esperados
    campos_sql_esperados = set()
    if execucao.template_sql:
        try:
            # Extrai campos do SELECT usando análise simples
            from .utils import mapear_campos_sql_para_dinamicos
            mapeamento = mapear_campos_sql_para_dinamicos(execucao.template_sql.template)
            campos_sql_esperados = set(mapeamento.get('campos_dinamicos_possiveis', []))
        except:
            pass
    
    # Informações para interface
    info = {
        'total_variaveis_unicas': len(todas_variaveis_dinamicas),
        'total_clientes_execucao': total_clientes_execucao,
        'clientes_com_dinamicos': clientes_com_dinamicos,
        'percentual_com_dinamicos': round((clientes_com_dinamicos / total_clientes_execucao * 100) if total_clientes_execucao > 0 else 0, 1),
        'variaveis_encontradas': list(todas_variaveis_dinamicas),
        'exemplos_variaveis': exemplos_variaveis,
        'campos_sql_esperados': list(campos_sql_esperados),
        'template_sql_nome': execucao.template_sql.titulo if execucao.template_sql else 'N/A',
        'tem_dados_dinamicos': len(todas_variaveis_dinamicas) > 0,
        
        # Para uso em HSM e Flow
        'variaveis_hsm_disponiveis': [
            {
                'nome_hsm': f'dinamico_{var}',
                'nome_direto': var,
                'exemplo_uso_hsm': f'{{{{{var}}}}}',
                'exemplo_valor': exemplos_variaveis[var]['valor_exemplo']
            }
            for var in todas_variaveis_dinamicas
        ],
        
        # Meta informações
        'consulta_executada_com_api': not execucao.pular_consulta_api if hasattr(execucao, 'pular_consulta_api') else True,
        'status_execucao': execucao.status,
        'pode_usar_variaveis': execucao.status in ['concluida', 'erro'] and len(todas_variaveis_dinamicas) > 0
    }
    
    return info

def verificar_variaveis_vazias(variaveis_hsm, configuracao_variaveis, dados_cliente):
    """
    Verifica se alguma variável necessária está vazia nos dados do cliente
    
    Args:
        variaveis_hsm: Dict com variáveis preparadas para envio
        configuracao_variaveis: Mapeamento de variáveis HSM -> campos cliente
        dados_cliente: Dados do cliente para verificação
    
    Returns:
        bool: True se alguma variável obrigatória estiver vazia
    """
    for var_hsm, campo_cliente in configuracao_variaveis.items():
        valor = dados_cliente.get(campo_cliente, '')
        # Considera vazio se for None, string vazia ou só espaços
        if not valor or (isinstance(valor, str) and not valor.strip()):
            logger.info(f"Variável {var_hsm} (campo {campo_cliente}) está vazia para cliente {dados_cliente.get('codigo_cliente')}")
            return True
    return False

def verificar_pix_vazio_para_pagamento(template_hsm, dados_cliente):
    """
    Verifica especificamente se o PIX está vazio para templates de pagamento
    
    Args:
        template_hsm: Template HSM sendo usado
        dados_cliente: Dados do cliente para verificação
    
    Returns:
        bool: True se for template de pagamento e PIX estiver vazio
    """
    # Verifica se é template de pagamento
    if not hasattr(template_hsm, 'tipo_template') or template_hsm.tipo_template != 'pagamento':
        return False
    
    # Verifica se o campo PIX está vazio
    pix_value = dados_cliente.get('pix', '') or dados_cliente.get('pix_copia_cola', '')
    pix_vazio = not pix_value or (isinstance(pix_value, str) and not pix_value.strip())
    
    if pix_vazio:
        logger.info(f"🔍 PIX vazio detectado para cliente {dados_cliente.get('codigo_cliente')} em template de pagamento {template_hsm.nome}")
        return True
    
    return False

def preparar_flow_variaveis(cliente, envio_matrix=None):
    """
    Prepara todas as variáveis disponíveis do cliente para enviar ao flow
    INCLUI TODAS AS VARIÁVEIS DINÂMICAS AUTOMATICAMENTE
    
    Args:
        cliente: Objeto ClienteConsultado
        envio_matrix: Objeto EnvioHSMMatrix opcional para configurações extras
    
    Returns:
        dict: Variáveis formatadas para flow_variaveis (campos fixos + dinâmicos)
    """
    flow_vars = {
        # Dados básicos do cliente
        "codigo_cliente": serializar_valor_para_json(cliente.codigo_cliente),
        "nome_cliente": serializar_valor_para_json(cliente.nome_razaosocial),
        "telefone": serializar_valor_para_json(cliente.telefone_corrigido),
        
        # Dados da fatura
        "id_fatura": serializar_valor_para_json(cliente.id_fatura),
        "valor_fatura": serializar_valor_para_json(cliente.valor_fatura),
        "vencimento_fatura": serializar_valor_para_json(cliente.vencimento_fatura),
        
        # Dados de pagamento
        "codigo_barras": serializar_valor_para_json(cliente.codigo_barras),
        "pix_copia_cola": serializar_valor_para_json(cliente.pix),
        "link_boleto": serializar_valor_para_json(cliente.link_boleto),
        
        # Dados da empresa
        "empresa": serializar_valor_para_json(cliente.credencial_banco.titulo if cliente.credencial_banco else ''),
    }
    
    # NOVO: Adiciona TODAS as variáveis dinâmicas do cliente ao Flow
    dados_dinamicos = cliente.get_todos_dados_dinamicos()
    if dados_dinamicos:
        print(f"   🌊 Adicionando {len(dados_dinamicos)} variáveis dinâmicas ao Flow:")
        for chave, valor in dados_dinamicos.items():
            # Adiciona com prefixo para identificação
            nome_variavel = f"dinamico_{chave}"
            flow_vars[nome_variavel] = serializar_valor_para_json(valor)
            print(f"      • {nome_variavel}: {valor}")
            
            # Também adiciona sem prefixo para compatibilidade
            flow_vars[chave] = serializar_valor_para_json(valor)
    
    # Adiciona metadados úteis
    flow_vars.update({
        "total_variaveis_dinamicas": len(dados_dinamicos),
        "data_ultima_atualizacao": serializar_valor_para_json(cliente.data_atualizacao),
        "source": "sistema_campanhas"  # Identifica origem dos dados
    })
    
    # Remove variáveis vazias ou None
    flow_vars = {k: v for k, v in flow_vars.items() if v and v != ''}
    
    # Adiciona variáveis extras da configuração de pagamento se existir
    if envio_matrix and hasattr(envio_matrix, 'configuracao_pagamento_hsm') and envio_matrix.configuracao_pagamento_hsm:
        config_pagamento = envio_matrix.configuracao_pagamento_hsm
        if config_pagamento.variaveis_flow_padrao:
            flow_vars.update(config_pagamento.variaveis_flow_padrao)
    
    # Adiciona dados de pagamento se for template de pagamento
    if envio_matrix and hasattr(envio_matrix, 'configuracao_pagamento_hsm') and envio_matrix.configuracao_pagamento_hsm:
        config = envio_matrix.configuracao_pagamento_hsm
        flow_vars.update({
            "razao_social_empresa": config.razao_social_empresa,
            "cnpj_empresa": config.cnpj_empresa,
            "nome_produto": config.nome_produto_padrao,
            "tipo_produto": config.tipo_produto,
            "val_imposto": str(config.val_imposto),
            "val_desconto": str(config.val_desconto)
        })
    elif envio_matrix:
        # Se não tem configuração, usa os campos diretos
        if envio_matrix.razao_social_empresa:
            flow_vars["razao_social_empresa"] = envio_matrix.razao_social_empresa
        if envio_matrix.cnpj_empresa:
            flow_vars["cnpj_empresa"] = envio_matrix.cnpj_empresa
        if envio_matrix.nome_produto_padrao:
            flow_vars["nome_produto"] = envio_matrix.nome_produto_padrao
    
    return flow_vars

def enviar_hsm_matrix_django(matrix_config, hsm_template, cliente, variaveis_hsm, envio_matrix=None, envio_individual=None):
    """
    Função para envio de HSM via API Matrix integrada ao Django
    
    Args:
        matrix_config: Objeto MatrixAPIConfig com configurações da API
        hsm_template: Objeto HSMTemplate com dados do template
        cliente: Objeto ClienteConsultado com dados do cliente
        variaveis_hsm: Dict com variáveis para substituição no HSM
        envio_matrix: Objeto EnvioHSMMatrix opcional para flow_variaveis
    
    Returns:
        dict: Resultado da operação com success, error, status_code, data
    """
    try:
        # Configuração da API
        base_url = matrix_config.base_url.rstrip('/')
        headers = {
            'Authorization': matrix_config.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # ✅ CORREÇÃO: Criação do contato com tratamento de espaços
        nome_cliente = cliente.nome_razaosocial or "Cliente"
        if isinstance(nome_cliente, str) and ' ' in nome_cliente:
            print(f"🔍 CONTATO COM NOME COM ESPAÇO: '{nome_cliente}'")
            # Normaliza o nome para o contato
            nome_cliente = ' '.join(nome_cliente.strip().split())
            print(f"🔧 NOME NORMALIZADO PARA CONTATO: '{nome_cliente}'")

        contato = {
            "nome": nome_cliente,
            "telefone": cliente.telefone_corrigido or ""
        }

        print(f"📞 CONTATO FINAL: {contato}")
        
        # Construção do payload
        payload = {
            "cod_conta": matrix_config.cod_conta,
            "hsm": hsm_template.hsm_id,
            "tipo_envio": hsm_template.tipo_envio or 1,  # Default: atendimento automático
            "cod_flow": hsm_template.cod_flow or 0,
            "start_flow": 1,  # Inicia flow automaticamente
            "contato": contato,
            "bol_incluir_atual": 1  # Inclui mesmo com atendimento em andamento
        }
        
        # Adiciona variáveis se fornecidas (garantindo serialização)
        if variaveis_hsm:
            print(f"🔍 DEBUG: Processando {len(variaveis_hsm)} variáveis HSM para API:")
            variaveis_serializadas = {}
            for chave, valor in variaveis_hsm.items():
                valor_serializado = serializar_valor_para_json(valor)
                
                # ✅ CORREÇÃO: Validação extra para nomes com espaços
                if isinstance(valor, str) and ' ' in valor:
                    print(f"   🔍 NOME COM ESPAÇO DETECTADO: '{valor}'")
                    # Testa se o valor foi serializado corretamente
                    if not valor_serializado or valor_serializado.strip() == '':
                        print(f"   ❌ ERRO: Serialização falhou para '{valor}'")
                        # Fallback: usar valor original limpo
                        valor_serializado = ' '.join(str(valor).strip().split())
                        print(f"   🔧 FALLBACK: Usando '{valor_serializado}'")
                    else:
                        print(f"   ✅ SERIALIZAÇÃO OK: '{valor}' → '{valor_serializado}'")
                
                variaveis_serializadas[str(chave)] = valor_serializado
                print(f"   📝 {chave}: '{valor}' → '{valor_serializado}'")
            
            payload["variaveis"] = variaveis_serializadas
            print(f"✅ Payload[variaveis] final: {payload['variaveis']}")
            
            # ✅ CORREÇÃO: Log específico para debug de nomes
            for chave, valor in variaveis_serializadas.items():
                if isinstance(valor, str) and ' ' in valor:
                    print(f"   🎯 VARIÁVEL COM ESPAÇO FINAL: {chave} = '{valor}' (len: {len(valor)})")
        else:
            print("⚠️  AVISO: Nenhuma variável HSM fornecida!")
        
        # Adiciona flow_variaveis com todas as informações do cliente
        flow_variaveis = preparar_flow_variaveis(cliente, envio_matrix)
        if flow_variaveis:
            payload["flow_variaveis"] = flow_variaveis
            logger.info(f"Adicionadas {len(flow_variaveis)} variáveis ao flow para cliente {cliente.codigo_cliente}")
            
            # Salva as variáveis do flow no envio individual para referência futura
            if hasattr(envio_individual, 'flow_variaveis_enviadas'):
                envio_individual.flow_variaveis_enviadas = flow_variaveis
                envio_individual.save()
        
        # URL do endpoint
        url = f"{base_url}/rest/v1/sendHsm"
        
        logger.info(f"Enviando HSM para {cliente.codigo_cliente} - {cliente.nome_razaosocial}")
        logger.debug(f"URL: {url}, Payload: {payload}")
        
        # Executa a requisição
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        # Retorna sucesso
        return {
            "success": True,
            "status_code": response.status_code,
            "data": response.json(),
            "error": None
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao enviar HSM para {cliente.codigo_cliente}")
        return {
            "success": False,
            "error": "Timeout na requisição - servidor não respondeu em 30 segundos",
            "status_code": None,
            "data": None
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de requisição ao enviar HSM para {cliente.codigo_cliente}: {e}")
        return {
            "success": False,
            "error": f"Erro de rede: {str(e)}",
            "status_code": getattr(response, 'status_code', None),
            "data": getattr(response, 'text', None)
        }
        
    except Exception as e:
        logger.error(f"Erro inesperado ao enviar HSM para {cliente.codigo_cliente}: {e}")
        return {
            "success": False,
            "error": f"Erro inesperado: {str(e)}",
            "status_code": None,
            "data": None
        }

def enviar_hsm_pagamento_matrix_django(matrix_config, hsm_template, cliente, variaveis_hsm, dados_pagamento, url_file, envio_matrix=None, envio_individual=None):
    """
    Função para envio de HSM com dados de pagamento via API Matrix
    
    Args:
        matrix_config: Objeto MatrixAPIConfig com configurações da API
        hsm_template: Objeto HSMTemplate com dados do template
        cliente: Objeto ClienteConsultado com dados do cliente
        variaveis_hsm: Dict com variáveis para substituição no HSM
        dados_pagamento: Dict com dados específicos do pagamento
        url_file: String com URL do arquivo PDF do boleto
        envio_matrix: Objeto EnvioHSMMatrix opcional para flow_variaveis
    
    Returns:
        dict: Resultado da operação com success, error, status_code, data
    """
    try:
        # Validações de entrada
        if not matrix_config or not hsm_template or not cliente:
            raise ValueError("Parâmetros obrigatórios faltando: matrix_config, hsm_template ou cliente")
        
        if not dados_pagamento or not isinstance(dados_pagamento, dict):
            raise ValueError("dados_pagamento deve ser um dicionário válido")
        
        # Configuração da API
        base_url = matrix_config.base_url.rstrip('/')
        headers = {
            'Authorization': matrix_config.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Validação do telefone
        telefone = cliente.telefone_corrigido or ""
        if not telefone:
            logger.warning(f"Cliente {cliente.codigo_cliente} não possui telefone válido")
        
        # Criação do contato
        contato = {
            "nome": str(cliente.nome_razaosocial or "Cliente"),
            "telefone": str(telefone)
        }
        
        # Validação da URL do arquivo
        url_file_valid = str(url_file or "")
        if not url_file_valid:
            logger.warning(f"Cliente {cliente.codigo_cliente} não possui link do boleto")
        
        # Construção do payload para HSM de pagamento
        payload = {
            "cod_conta": int(matrix_config.cod_conta),
            "hsm": int(hsm_template.hsm_id),
            "tipo_envio": int(hsm_template.tipo_envio or 2),  # Default: notificação para pagamento
            "url_file": url_file_valid,
            "hsm_parametros": dados_pagamento,
            "contato": contato
        }
        
        # Adiciona variáveis se fornecidas (garantindo serialização)
        if variaveis_hsm and isinstance(variaveis_hsm, dict):
            variaveis_serializadas = {}
            for chave, valor in variaveis_hsm.items():
                variaveis_serializadas[str(chave)] = serializar_valor_para_json(valor)
            payload["variaveis"] = variaveis_serializadas
        
        # Adiciona flow_variaveis com todas as informações do cliente
        flow_variaveis = preparar_flow_variaveis(cliente, envio_matrix)
        if flow_variaveis:
            payload["flow_variaveis"] = flow_variaveis
            logger.info(f"Adicionadas {len(flow_variaveis)} variáveis ao flow para cliente {cliente.codigo_cliente}")
            
            # Salva as variáveis do flow no envio individual para referência futura
            if hasattr(envio_individual, 'flow_variaveis_enviadas'):
                envio_individual.flow_variaveis_enviadas = flow_variaveis
                envio_individual.save()
        
        # URL do endpoint
        url = f"{base_url}/rest/v1/sendHsm"
        
        logger.info(f"Enviando HSM de pagamento para {cliente.codigo_cliente} - {cliente.nome_razaosocial}")
        logger.info(f"Template HSM ID: {hsm_template.hsm_id}, Tipo Envio: {hsm_template.tipo_envio}")
        logger.debug(f"URL: {url}")
        logger.debug(f"Payload completo: {payload}")
        
        # ============= LOGS DE ENVIO DETALHADOS =============
        try:
            print("=" * 80)
            print("🚀 ENVIANDO HSM DE PAGAMENTO")
            print("=" * 80)
            print(f"📞 Cliente: {getattr(cliente, 'codigo_cliente', 'N/A')} - {getattr(cliente, 'nome_razaosocial', 'N/A')}")
            print(f"📱 Telefone: {telefone}")
            print(f"🏷️  Template HSM ID: {getattr(hsm_template, 'hsm_id', 'N/A')}")
            print(f"📊 Cod Conta: {getattr(matrix_config, 'cod_conta', 'N/A')}")
            print(f"📄 URL do Arquivo: {url_file_valid}")
            print("-" * 80)
            print("📦 PAYLOAD COMPLETO:")
            import json
            print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
            print("=" * 80)
        except Exception as log_error:
            print(f"Erro nos logs: {log_error}")
        
        # Executa a requisição
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # Log da resposta para debug
        try:
            print(f"📈 Status da resposta: {response.status_code}")
            print(f"📝 Resposta da API: {response.text}")
            print("=" * 80)
        except Exception as log_error:
            print(f"Erro no log da resposta: {log_error}")
        
        logger.info(f"HSM de pagamento enviado - Status: {response.status_code}")
        logger.info(f"Cliente: {cliente.codigo_cliente} - Resposta: {response.text}")
        
        response.raise_for_status()
        
        # Retorna sucesso
        return {
            "success": True,
            "status_code": response.status_code,
            "data": response.json(),
            "error": None
        }
        
    except requests.exceptions.Timeout:
        print(f"⏱️  TIMEOUT: Servidor não respondeu em 30 segundos para cliente {cliente.codigo_cliente}")
        print("=" * 80)
        logger.error(f"Timeout ao enviar HSM de pagamento para {cliente.codigo_cliente}")
        return {
            "success": False,
            "error": "Timeout na requisição - servidor não respondeu em 30 segundos",
            "status_code": None,
            "data": None
        }
        
    except requests.exceptions.RequestException as e:
        print(f"🌐 ERRO DE REDE para cliente {cliente.codigo_cliente}: {str(e)}")
        print("=" * 80)
        logger.error(f"Erro de requisição ao enviar HSM de pagamento para {cliente.codigo_cliente}: {e}")
        return {
            "success": False,
            "error": f"Erro de rede: {str(e)}",
            "status_code": getattr(response, 'status_code', None),
            "data": getattr(response, 'text', None)
        }
        
    except Exception as e:
        print(f"❌ ERRO INESPERADO para cliente {cliente.codigo_cliente}: {str(e)}")
        print("=" * 80)
        logger.error(f"Erro inesperado ao enviar HSM de pagamento para {cliente.codigo_cliente}: {e}")
        return {
            "success": False,
            "error": f"Erro inesperado: {str(e)}",
            "status_code": None,
            "data": None
        }

def debug_payload_pagamento(cliente, envio_matrix):
    """
    Função de debug para mostrar como o payload deveria ficar
    """
    try:
        print("\n" + "=" * 80)
        print("🔍 DEBUG: PREPARANDO DADOS DE PAGAMENTO")
        print("=" * 80)
        
        # Dados do cliente - com proteção contra None
        print("👤 DADOS DO CLIENTE:")
        print(f"   Código: {getattr(cliente, 'codigo_cliente', 'N/A')}")
        print(f"   Nome: {getattr(cliente, 'nome_razaosocial', 'N/A')}")
        print(f"   Telefone: {getattr(cliente, 'telefone_corrigido', 'N/A')}")
        print(f"   Valor Fatura: {getattr(cliente, 'valor_fatura', 'N/A')}")
        print(f"   PIX: {getattr(cliente, 'pix', 'N/A')}")
        print(f"   Link Boleto: {getattr(cliente, 'link_boleto', 'N/A')}")
        print(f"   ID Fatura: {getattr(cliente, 'id_fatura', 'N/A')}")
        
        # Dados da configuração - com proteção contra None
        print("\n🏢 CONFIGURAÇÃO DO ENVIO:")
        print(f"   Razão Social: {getattr(envio_matrix, 'razao_social_empresa', 'N/A')}")
        print(f"   CNPJ: {getattr(envio_matrix, 'cnpj_empresa', 'N/A')}")
        print(f"   Nome Produto: {getattr(envio_matrix, 'nome_produto_padrao', 'N/A')}")
        
        print("\n🔧 GERANDO DADOS REAIS...")
        dados_reais = preparar_dados_pagamento(cliente, envio_matrix)
        
        print("\n📦 DADOS REAIS PREPARADOS (hsm_parametros):")
        try:
            import json
            print(json.dumps(dados_reais, indent=2, ensure_ascii=False, default=str))
        except Exception as json_error:
            print(f"Erro ao serializar JSON: {json_error}")
            print(f"Dados brutos: {dados_reais}")
        
        print("=" * 80)
        
        logger.info("=== DADOS REAIS PREPARADOS ===")
        logger.info(f"Dados reais: {dados_reais}")
        
        return dados_reais
        
    except Exception as e:
        print(f"❌ ERRO no debug_payload_pagamento: {e}")
        logger.error(f"Erro no debug_payload_pagamento: {e}")
        # Retorna dados básicos mesmo em caso de erro
        return preparar_dados_pagamento(cliente, envio_matrix)

def validar_configuracao_pagamento(envio_matrix):
    """
    Valida se a configuração de pagamento está completa
    """
    erros = []
    
    # Verifica se há configuração de pagamento predefinida
    if hasattr(envio_matrix, 'configuracao_pagamento_hsm') and envio_matrix.configuracao_pagamento_hsm:
        config = envio_matrix.configuracao_pagamento_hsm
        logger.info(f"Validando configuração de pagamento predefinida: {config.nome}")
        
        # Valida campos da configuração predefinida
        if not config.razao_social_empresa:
            erros.append("Razão Social da Empresa não configurada na configuração predefinida")
        
        if not config.cnpj_empresa:
            erros.append("CNPJ da Empresa não configurado na configuração predefinida")
        
        if not config.nome_produto_padrao:
            erros.append("Nome do Produto Padrão não configurado na configuração predefinida")
    else:
        # Valida campos diretos do envio_matrix (comportamento anterior)
        logger.info(f"Validando configuração de pagamento manual do envio {envio_matrix.id}")
        
        if not envio_matrix.razao_social_empresa:
            erros.append("Razão Social da Empresa não configurada")
        
        if not envio_matrix.cnpj_empresa:
            erros.append("CNPJ da Empresa não configurado")
        
        if not envio_matrix.nome_produto_padrao:
            erros.append("Nome do Produto Padrão não configurado")
    
    if erros:
        logger.error(f"Erros na configuração de pagamento do envio {envio_matrix.id}: {erros}")
        return False, erros
    
    logger.info(f"Configuração de pagamento válida para envio {envio_matrix.id}")
    return True, []

def preparar_dados_pagamento(cliente, envio_matrix):
    """
    Prepara os dados de pagamento baseados nos dados do cliente e configurações do envio
    
    Args:
        cliente: Objeto ClienteConsultado com dados do cliente
        envio_matrix: Objeto EnvioHSMMatrix com configurações do envio
    
    Returns:
        dict: Dados formatados para o campo hsm_parametros
    """
    try:
        try:
            print("\n🔧 ETAPA 1: VALIDANDO CAMPOS OBRIGATÓRIOS")
        except:
            pass  # Não deixa erro de print quebrar a função
        
        # Verifica se há configuração de pagamento predefinida
        if hasattr(envio_matrix, 'configuracao_pagamento_hsm') and envio_matrix.configuracao_pagamento_hsm:
            config = envio_matrix.configuracao_pagamento_hsm
            logger.info(f"Usando configuração de pagamento predefinida: {config.nome}")
            
            # Usa os dados da configuração
            razao_social = config.razao_social_empresa
            cnpj_empresa = config.cnpj_empresa
            nome_produto = config.nome_produto_padrao
            tipo_produto = config.tipo_produto
            val_imposto = float(config.val_imposto)
            val_desconto = float(config.val_desconto)
        else:
            # Usa os campos diretos do envio_matrix (comportamento anterior)
            razao_social = getattr(envio_matrix, 'razao_social_empresa', None) or "Empresa"
            cnpj_empresa = getattr(envio_matrix, 'cnpj_empresa', None) or ""
            nome_produto = getattr(envio_matrix, 'nome_produto_padrao', None) or f"Fatura {razao_social}"
            tipo_produto = "digital-goods"
            val_imposto = float(getattr(envio_matrix, 'val_imposto', 0) or 0)
            val_desconto = float(getattr(envio_matrix, 'val_desconto', 0) or 0)
        
        # Validações de campos obrigatórios
        pix_codigo = getattr(cliente, 'pix', None) or ""
        if not pix_codigo:
            try:
                print(f"⚠️  AVISO: Cliente {getattr(cliente, 'codigo_cliente', 'N/A')} não possui PIX válido")
            except:
                pass
            logger.warning(f"Cliente {getattr(cliente, 'codigo_cliente', 'N/A')} não possui PIX válido")
        else:
            try:
                print(f"✅ PIX válido encontrado: {str(pix_codigo)[:20]}...")
            except:
                pass
        
        if not cnpj_empresa:
            try:
                print(f"⚠️  AVISO: Envio {getattr(envio_matrix, 'id', 'N/A')} não possui CNPJ configurado")
            except:
                pass
            logger.warning(f"Envio {getattr(envio_matrix, 'id', 'N/A')} não possui CNPJ configurado")
        else:
            try:
                print(f"✅ CNPJ válido: {cnpj_empresa}")
            except:
                pass
        
        # Valor da fatura com validação
        valor_unitario = safe_decimal_to_float(getattr(cliente, 'valor_fatura', None), 1.00)
        if valor_unitario <= 0:
            try:
                print(f"⚠️  AVISO: Cliente {getattr(cliente, 'codigo_cliente', 'N/A')} possui valor de fatura inválido: {getattr(cliente, 'valor_fatura', 'N/A')}")
            except:
                pass
            logger.warning(f"Cliente {getattr(cliente, 'codigo_cliente', 'N/A')} possui valor de fatura inválido: {getattr(cliente, 'valor_fatura', 'N/A')}")
            valor_unitario = 1.00
        else:
            try:
                print(f"✅ Valor da fatura: R$ {valor_unitario:.2f}")
            except:
                pass
        
        # Dados básicos do PIX
        pix_data = {
            "codigo": str(pix_codigo),
            "nom_empresa": str(razao_social),
            "chave": str(cnpj_empresa),
            "chave_tipo": "CNPJ"
        }
        
        # Item do pedido
        pedido_item = {
            "id_produto": str(getattr(cliente, 'codigo_cliente', None) or "0"),
            "nom_produto": str(nome_produto),
            "val_unitario": float(valor_unitario),
            "num_quantidade": 1
        }
        
        # ID do pedido/boleto
        pedido_id = getattr(cliente, 'id_fatura', None) or getattr(cliente, 'codigo_cliente', None) or "0"
        
        # Informações do pedido
        pedido_info = {
            "pedido_id": str(pedido_id),
            "tipo": tipo_produto,
            "val_imposto": val_imposto,
            "val_desconto": val_desconto,
            "pedido_itens": [pedido_item],
            "pix": pix_data
        }
        
        # Dados completos para hsm_parametros
        dados_pagamento = {
            "pedido_info": pedido_info
        }
        
        # Adiciona configurações específicas se existirem
        if hasattr(envio_matrix, 'configuracao_pagamento') and envio_matrix.configuracao_pagamento:
            try:
                config_adicional = envio_matrix.configuracao_pagamento
                if isinstance(config_adicional, dict):
                    dados_pagamento.update(config_adicional)
            except Exception as e:
                logger.error(f"Erro ao processar configuração adicional de pagamento: {e}")
        
        logger.debug(f"Dados de pagamento preparados para cliente {getattr(cliente, 'codigo_cliente', 'N/A')}: {dados_pagamento}")
        
        return dados_pagamento
        
    except Exception as e:
        logger.error(f"Erro ao preparar dados de pagamento para cliente {cliente.codigo_cliente}: {e}")
        # Retorna dados mínimos em caso de erro
        return {
            "pedido_info": {
                "pedido_id": str(cliente.codigo_cliente or "0"),
                "tipo": "digital-goods",
                "val_imposto": 0.0,
                "val_desconto": 0.0,
                "pedido_itens": [{
                    "id_produto": str(cliente.codigo_cliente or "0"),
                    "nom_produto": "Fatura",
                    "val_unitario": 1.00,
                    "num_quantidade": 1
                }],
                "pix": {
                    "codigo": "",
                    "nom_empresa": "Empresa",
                    "chave": "",
                    "chave_tipo": "CNPJ"
                }
            }
        }

def processar_envio_duplo_hsm(envio_individual, envio_matrix, matriz_config, template_hsm, variaveis_hsm):
    """
    Processa o envio duplo de HSM para um cliente específico
    
    Args:
        envio_individual: Objeto EnvioHSMIndividual do primeiro HSM
        envio_matrix: Objeto EnvioHSMMatrix com configurações
        matriz_config: Configuração da API Matrix
        template_hsm: Template do primeiro HSM
        variaveis_hsm: Variáveis do primeiro HSM
    
    Returns:
        tuple: (resultado_primeiro, resultado_segundo)
    """
    cliente = envio_individual.cliente
    resultado_primeiro = None
    resultado_segundo = None
    
    try:
        print(f"\n🎯 INICIANDO ENVIO DUPLO PARA: {getattr(cliente, 'codigo_cliente', 'N/A')}")
        
        # ========= PRIMEIRO HSM =========
        logger.info(f"Enviando primeiro HSM para cliente {cliente.codigo_cliente}")
        
        # Verifica se deve usar contingência para o primeiro HSM também
        template_primeiro_a_usar = template_hsm
        variaveis_primeiro_a_usar = variaveis_hsm
        
        # Verifica PIX vazio especificamente para template de pagamento
        dados_cliente_duplo = {
            'codigo_cliente': getattr(cliente, 'codigo_cliente', ''),
            'pix': getattr(cliente, 'pix', ''),
            'pix_copia_cola': getattr(cliente, 'pix', '')
        }
        
        if verificar_pix_vazio_para_pagamento(template_hsm, dados_cliente_duplo):
            if envio_matrix.hsm_template_contingencia:
                logger.info(f"💳 PIX vazio detectado no envio duplo - usando template de contingência para primeiro HSM do cliente {cliente.codigo_cliente}")
                template_primeiro_a_usar = envio_matrix.hsm_template_contingencia
                
                # Prepara variáveis de contingência se configuradas
                if envio_matrix.configuracao_variaveis_contingencia:
                    variaveis_primeiro_a_usar = {}
                    for var_hsm, campo_cliente in envio_matrix.configuracao_variaveis_contingencia.items():
                        valor = envio_individual.variaveis_utilizadas.get(campo_cliente, '')
                        variaveis_primeiro_a_usar[var_hsm] = str(valor)
            else:
                logger.warning(f"💳 PIX vazio no envio duplo para cliente {cliente.codigo_cliente}, mas não há template de contingência configurado")
        
        if template_primeiro_a_usar.tipo_template == 'pagamento':
            # Prepara dados de pagamento para o primeiro HSM
            dados_pagamento = debug_payload_pagamento(cliente, envio_matrix)
            url_file = getattr(cliente, 'link_boleto', None) or ""
            
            resultado_primeiro = enviar_hsm_pagamento_matrix_django(
                matrix_config=matriz_config,
                hsm_template=template_primeiro_a_usar,
                cliente=cliente,
                variaveis_hsm=variaveis_primeiro_a_usar,
                dados_pagamento=dados_pagamento,
                url_file=url_file,
                envio_matrix=envio_matrix,
                envio_individual=envio_individual
            )
        else:
            resultado_primeiro = enviar_hsm_matrix_django(
                matrix_config=matriz_config,
                hsm_template=template_primeiro_a_usar,
                cliente=cliente,
                variaveis_hsm=variaveis_primeiro_a_usar,
                envio_matrix=envio_matrix,
                envio_individual=envio_individual
            )
        
        # Verifica se o primeiro HSM foi enviado com sucesso
        if not resultado_primeiro['success']:
            logger.error(f"Erro no primeiro HSM para {cliente.codigo_cliente}: {resultado_primeiro.get('error')}")
            envio_individual.marcar_erro(f"Erro no primeiro HSM: {resultado_primeiro.get('error')}", resultado_primeiro.get('data'))
            return resultado_primeiro, None
        
        # Marca primeiro HSM como enviado
        envio_individual.marcar_enviado(resultado_primeiro.get('data'))
        logger.info(f"Primeiro HSM enviado com sucesso para {cliente.codigo_cliente}")
        
        # ========= AGUARDA INTERVALO =========
        intervalo = envio_matrix.intervalo_segundo_hsm or 3
        logger.info(f"Aguardando {intervalo} segundos antes do segundo HSM...")
        time.sleep(intervalo)
        
        # ========= SEGUNDO HSM =========
        logger.info(f"Enviando segundo HSM para cliente {cliente.codigo_cliente}")
        
        # Cria registro do segundo envio
        envio_segundo = EnvioHSMIndividual.objects.create(
            envio_matrix=envio_matrix,
            cliente=cliente,
            status='enviando',
            hsm_enviado='segundo',
            envio_relacionado=envio_individual,
            variaveis_utilizadas=envio_individual.variaveis_utilizadas  # Pode ser diferente
        )
        
        # Prepara variáveis para o segundo HSM
        template_segundo = envio_matrix.hsm_template_segundo
        variaveis_segundo = {}
        
        if envio_matrix.configuracao_variaveis_segundo:
            for var_hsm, campo_cliente in envio_matrix.configuracao_variaveis_segundo.items():
                valor = envio_individual.variaveis_utilizadas.get(campo_cliente, '')
                variaveis_segundo[var_hsm] = str(valor)
        
        # Atualiza as variáveis utilizadas no segundo envio
        envio_segundo.variaveis_utilizadas = variaveis_segundo
        envio_segundo.save()
        
        # Envia o segundo HSM
        if template_segundo.tipo_template == 'pagamento':
            # Usa dados de pagamento específicos para o segundo HSM
            dados_pagamento_segundo = preparar_dados_pagamento_segundo(cliente, envio_matrix)
            url_file_segundo = getattr(cliente, 'link_boleto', None) or ""
            
            resultado_segundo = enviar_hsm_pagamento_matrix_django(
                matrix_config=matriz_config,
                hsm_template=template_segundo,
                cliente=cliente,
                variaveis_hsm=variaveis_segundo,
                dados_pagamento=dados_pagamento_segundo,
                url_file=url_file_segundo,
                envio_matrix=envio_matrix,
                envio_individual=envio_segundo
            )
        else:
            resultado_segundo = enviar_hsm_matrix_django(
                matrix_config=matriz_config,
                hsm_template=template_segundo,
                cliente=cliente,
                variaveis_hsm=variaveis_segundo,
                envio_matrix=envio_matrix,
                envio_individual=envio_segundo
            )
        
        # Processa resultado do segundo HSM
        if resultado_segundo['success']:
            envio_segundo.marcar_enviado(resultado_segundo.get('data'))
            logger.info(f"Segundo HSM enviado com sucesso para {cliente.codigo_cliente}")
        else:
            erro_msg = resultado_segundo.get('error', 'Erro desconhecido no segundo HSM')
            envio_segundo.marcar_erro(erro_msg, resultado_segundo.get('data'))
            logger.error(f"Erro no segundo HSM para {cliente.codigo_cliente}: {erro_msg}")
        
        return resultado_primeiro, resultado_segundo
        
    except Exception as e:
        logger.error(f"Erro inesperado no envio duplo para {cliente.codigo_cliente}: {e}")
        # Se houve erro, marca o envio individual como erro
        erro_msg = f"Erro inesperado no envio duplo: {str(e)}"
        envio_individual.marcar_erro(erro_msg)
        return None, None

def preparar_dados_pagamento_segundo(cliente, envio_matrix):
    """
    Prepara os dados de pagamento específicos para o segundo HSM
    Similar à função preparar_dados_pagamento, mas usa os campos do segundo HSM
    """
    try:
        # Usa configurações específicas do segundo HSM se existirem, senão usa as do primeiro
        razao_social = getattr(envio_matrix, 'razao_social_empresa_segundo', None) or \
                      getattr(envio_matrix, 'razao_social_empresa', None) or "Empresa"
        cnpj_empresa = getattr(envio_matrix, 'cnpj_empresa_segundo', None) or \
                      getattr(envio_matrix, 'cnpj_empresa', None) or ""
        nome_produto = getattr(envio_matrix, 'nome_produto_padrao_segundo', None) or \
                      getattr(envio_matrix, 'nome_produto_padrao', None) or f"Fatura {razao_social}"
        
        # Valor da fatura com validação
        valor_unitario = safe_decimal_to_float(getattr(cliente, 'valor_fatura', None), 1.00)
        
        # Dados básicos do PIX
        pix_codigo = getattr(cliente, 'pix', None) or ""
        pix_data = {
            "codigo": str(pix_codigo),
            "nom_empresa": str(razao_social),
            "chave": str(cnpj_empresa),
            "chave_tipo": "CNPJ"
        }
        
        # Item do pedido
        pedido_item = {
            "id_produto": str(getattr(cliente, 'codigo_cliente', None) or "0"),
            "nom_produto": str(nome_produto),
            "val_unitario": float(valor_unitario),
            "num_quantidade": 1
        }
        
        pedido_id = getattr(cliente, 'id_fatura', None) or getattr(cliente, 'codigo_cliente', None) or "0"
        
        # Valores específicos do segundo HSM
        config_pagamento_segundo = getattr(envio_matrix, 'configuracao_pagamento_segundo', {})
        val_imposto = float(config_pagamento_segundo.get('val_imposto', 0) or 0)
        val_desconto = float(config_pagamento_segundo.get('val_desconto', 0) or 0)
        
        # Informações do pedido
        pedido_info = {
            "pedido_id": str(pedido_id),
            "tipo": "digital-goods",
            "val_imposto": val_imposto,
            "val_desconto": val_desconto,
            "pedido_itens": [pedido_item],
            "pix": pix_data
        }
        
        dados_pagamento = {
            "pedido_info": pedido_info
        }
        
        # Adiciona configurações específicas se existirem
        if config_pagamento_segundo:
            dados_pagamento.update(config_pagamento_segundo)
        
        logger.debug(f"Dados de pagamento do segundo HSM preparados para cliente {getattr(cliente, 'codigo_cliente', 'N/A')}")
        
        return dados_pagamento
        
    except Exception as e:
        logger.error(f"Erro ao preparar dados de pagamento do segundo HSM para cliente {cliente.codigo_cliente}: {e}")
        # Retorna dados mínimos em caso de erro
        return preparar_dados_pagamento(cliente, envio_matrix)

def processar_envio_hsm_background(envio_matrix_id, apenas_pendentes=False):
    """Processa o envio de HSM em background"""
    
    try:
        print("\n🚀 INICIANDO PROCESSAMENTO DE ENVIO HSM")
        print(f"📋 Envio ID: {envio_matrix_id}")
        print(f"🔄 Apenas pendentes: {'SIM' if apenas_pendentes else 'NÃO'}")
    except:
        pass  # Não deixa erro de print quebrar a função
    
    try:
        envio_matrix = EnvioHSMMatrix.objects.get(id=envio_matrix_id)
        
        try:
            print(f"✅ Envio encontrado: {envio_matrix}")
            print(f"📊 Template: {getattr(envio_matrix.hsm_template, 'nome_template', 'N/A')}")
            print(f"🏷️  Tipo Template: {getattr(envio_matrix.hsm_template, 'tipo_template', 'N/A')}")
            
            if getattr(envio_matrix.hsm_template, 'tipo_template', None) == 'pagamento':
                print("💳 TIPO DE ENVIO: PAGAMENTO HSM")
            else:
                print("📄 TIPO DE ENVIO: HSM PADRÃO")
        except:
            pass
        
        if apenas_pendentes:
            envio_matrix.atualizar_status('enviando', 'Reiniciando envio para clientes pendentes...')
            # Busca apenas envios individuais pendentes
            envios_a_processar = EnvioHSMIndividual.objects.filter(
                envio_matrix=envio_matrix,
                status='pendente'
            ).select_related('cliente')
            
            total_clientes = envios_a_processar.count()
            
            if total_clientes == 0:
                envio_matrix.atualizar_status('concluido', 'Nenhum cliente pendente encontrado.')
                return
                
        else:
            envio_matrix.atualizar_status('enviando', 'Iniciando envio de HSM...')
            
            # Busca clientes válidos para envio considerando se a API foi pulada
            if envio_matrix.consulta_execucao.pular_consulta_api:
                # Se API foi pulada, considera todos os clientes da execução
                consultas_sucesso = ConsultaCliente.objects.filter(
                    execucao=envio_matrix.consulta_execucao
                ).select_related('cliente')
                print(f"🔄 Envio HSM: API foi pulada, enviando para todos os {consultas_sucesso.count()} clientes")
            else:
                # Se API foi consultada, considera apenas sucessos
                consultas_sucesso = ConsultaCliente.objects.filter(
                    execucao=envio_matrix.consulta_execucao,
                    sucesso_api=True
                ).select_related('cliente')
                print(f"📡 Envio HSM: API foi consultada, enviando para {consultas_sucesso.count()} clientes com sucesso")
            
            total_clientes = consultas_sucesso.count()
            envio_matrix.total_clientes = total_clientes
            envio_matrix.save()
            
            if total_clientes == 0:
                envio_matrix.atualizar_status('erro', 'Nenhum cliente com dados válidos encontrado.')
                return
            
            # Cria registros individuais de envio
            envios_individuais = []
            for consulta in consultas_sucesso:
                cliente = consulta.cliente
                
                # Mapeia campos do cliente para variáveis HSM
                dados_cliente = {
                    'nome_razaosocial': cliente.nome_razaosocial,
                    'codigo_cliente': cliente.codigo_cliente,
                    'telefone_corrigido': cliente.telefone_corrigido,
                    'valor_fatura': cliente.valor_fatura,
                    'vencimento_fatura': cliente.vencimento_fatura,
                    'codigo_barras': cliente.codigo_barras,
                    'pix': cliente.pix,
                    'link_boleto': cliente.link_boleto,
                    'id_fatura': cliente.id_fatura
                }
                
                print(f"🔄 DEBUG: Mapeando campos do cliente {cliente.codigo_cliente} para HSM...")
                # CORRIGIDO: Passa o objeto Cliente completo em vez do dict limitado
                variaveis_cliente = mapear_campos_cliente_para_hsm(cliente)
                print(f"   ✅ Variáveis mapeadas: {len(variaveis_cliente)} itens")
                print(f"   📝 Lista completa: {list(variaveis_cliente.keys())}")
                
                # Mostra especificamente as variáveis dinâmicas
                variaveis_dinamicas_encontradas = [k for k in variaveis_cliente.keys() if k.startswith('dinamico_') or k not in ['nome_cliente', 'codigo_cliente', 'telefone', 'valor_fatura', 'vencimento_fatura', 'codigo_barras', 'pix_copia_cola', 'link_boleto', 'id_fatura', 'empresa']]
                if variaveis_dinamicas_encontradas:
                    print(f"   🎯 Variáveis dinâmicas encontradas: {variaveis_dinamicas_encontradas}")
                else:
                    print(f"   ⚠️  Nenhuma variável dinâmica encontrada!")
                
                envio_individual = EnvioHSMIndividual(
                    envio_matrix=envio_matrix,
                    cliente=cliente,
                    variaveis_utilizadas=variaveis_cliente,
                    status='pendente'
                )
                envios_individuais.append(envio_individual)
            
            # Salva todos os envios individuais
            EnvioHSMIndividual.objects.bulk_create(envios_individuais)
            
            # Define os envios a processar
            envios_a_processar = EnvioHSMIndividual.objects.filter(envio_matrix=envio_matrix)
        
        # Processa cada envio individual
        total_enviados = 0
        total_erros = 0
        
        matrix_config = envio_matrix.matrix_api_config
        template_hsm = envio_matrix.hsm_template
        
        for envio_individual in envios_a_processar:
            # Verifica se o envio foi cancelado
            envio_matrix.refresh_from_db()
            if envio_matrix.status_envio == 'cancelado':
                logger.info(f"Envio HSM {envio_matrix_id} foi cancelado pelo usuário")
                break
            
            envio_individual.status = 'enviando'
            envio_individual.save()
            
            try:
                cliente = envio_individual.cliente
                
                # Determina qual template usar baseado na disponibilidade das variáveis
                usar_contingencia = False
                template_a_usar = template_hsm
                configuracao_a_usar = envio_matrix.configuracao_variaveis
                motivo_contingencia = ""
                
                # Verifica se deve usar contingência - Prioridade 1: PIX vazio em template de pagamento
                pix_vazio_pagamento = verificar_pix_vazio_para_pagamento(template_hsm, envio_individual.variaveis_utilizadas)
                
                # Verifica se deve usar contingência - Prioridade 2: Variáveis vazias em geral
                variaveis_vazias = False
                if envio_matrix.configuracao_variaveis:
                    variaveis_vazias = verificar_variaveis_vazias(None, envio_matrix.configuracao_variaveis, envio_individual.variaveis_utilizadas)
                
                # Se PIX vazio em template de pagamento OU variáveis vazias, usa contingência
                if (pix_vazio_pagamento or variaveis_vazias) and envio_matrix.hsm_template_contingencia and envio_matrix.configuracao_variaveis_contingencia:
                    usar_contingencia = True
                    template_a_usar = envio_matrix.hsm_template_contingencia
                    configuracao_a_usar = envio_matrix.configuracao_variaveis_contingencia
                    
                    if pix_vazio_pagamento:
                        motivo_contingencia = "PIX vazio em template de pagamento"
                        logger.info(f"💳 Usando template de contingência para cliente {cliente.codigo_cliente} - {motivo_contingencia}")
                    else:
                        motivo_contingencia = "variáveis principais vazias"
                        logger.info(f"📝 Usando template de contingência para cliente {cliente.codigo_cliente} - {motivo_contingencia}")
                        
                elif pix_vazio_pagamento or variaveis_vazias:
                    # Problemas detectados mas não há contingência configurada
                    if pix_vazio_pagamento:
                        logger.warning(f"💳 PIX vazio para cliente {cliente.codigo_cliente} em template de pagamento, mas não há template de contingência configurado")
                    else:
                        logger.warning(f"📝 Variáveis vazias para cliente {cliente.codigo_cliente} mas não há template de contingência configurado")
                
                # Prepara variáveis baseadas na configuração escolhida
                variaveis_hsm = {}
                if configuracao_a_usar:
                    print(f"🔧 DEBUG: Preparando variáveis HSM a partir da configuração:")
                    print(f"   📋 Configuração: {configuracao_a_usar}")
                    print(f"   🎯 Variáveis disponíveis do cliente: {list(envio_individual.variaveis_utilizadas.keys())}")
                    
                    for var_hsm, campo_cliente in configuracao_a_usar.items():
                        valor = envio_individual.variaveis_utilizadas.get(campo_cliente, '')
                        
                        # ✅ CORREÇÃO CRÍTICA: Debug específico para nome_razaosocial
                        if campo_cliente == 'nome_razaosocial':
                            print(f"   🎯 PROCESSANDO CAMPO CRÍTICO: nome_razaosocial")
                            print(f"      • Valor encontrado: '{valor}' (tipo: {type(valor)}, len: {len(str(valor))})")
                            print(f"      • Variáveis disponíveis: {list(envio_individual.variaveis_utilizadas.keys())}")
                            
                            # Verifica se o valor está vazio e tenta alternativas
                            if not valor or valor.strip() == '':
                                print(f"      ❌ VALOR VAZIO! Tentando alternativas...")
                                # Tenta buscar com nome alternativo
                                valor_alt = envio_individual.variaveis_utilizadas.get('nome_cliente', '')
                                if valor_alt:
                                    print(f"      ✅ ENCONTRADO com chave alternativa 'nome_cliente': '{valor_alt}'")
                                    valor = valor_alt
                                else:
                                    print(f"      ❌ Nenhuma alternativa encontrada!")
                        
                        # ✅ CORREÇÃO: Tratamento especial para nomes com espaços
                        if isinstance(valor, str) and ' ' in valor:
                            print(f"   🔍 PROCESSANDO NOME COM ESPAÇO: '{valor}'")
                            # Limpa e normaliza o valor
                            valor_limpo = ' '.join(valor.strip().split())
                            variaveis_hsm[var_hsm] = valor_limpo
                            print(f"   🔧 VALOR NORMALIZADO: '{valor}' → '{valor_limpo}'")
                        else:
                            variaveis_hsm[var_hsm] = str(valor)
                        
                        print(f"   📝 {var_hsm} ← {campo_cliente}: '{variaveis_hsm[var_hsm]}'")
                    
                    print(f"✅ Variáveis HSM finais preparadas: {variaveis_hsm}")
                    print(f"🎯 TOTAL DE VARIÁVEIS HSM: {len(variaveis_hsm)} (apenas as mapeadas)")
                else:
                    print("⚠️  AVISO: Nenhuma configuração de variáveis encontrada!")
                    # ✅ CORREÇÃO: Se não há configuração, não envia variáveis HSM
                    variaveis_hsm = {}
                
                # Registra qual template está sendo usado e o motivo
                envio_individual.template_usado = 'contingencia' if usar_contingencia else 'principal'
                
                envio_individual.save()
                
                # ========= VERIFICA SE É ENVIO DUPLO =========
                if envio_matrix.habilitar_segundo_hsm and envio_matrix.hsm_template_segundo:
                    logger.info(f"🔄 ENVIO DUPLO habilitado para cliente {cliente.codigo_cliente}")
                    
                    # Validação se template de pagamento
                    if template_a_usar.tipo_template == 'pagamento':
                        config_valida, erros_config = validar_configuracao_pagamento(envio_matrix)
                        if not config_valida:
                            logger.error(f"Configuração inválida para envio de pagamento: {erros_config}")
                            envio_individual.status = 'erro'
                            envio_individual.erro_detalhado = f"Configuração inválida: {', '.join(erros_config)}"
                            envio_individual.save()
                            total_erros += 1
                            continue
                    
                    # Chama função de envio duplo
                    resultado_primeiro, resultado_segundo = processar_envio_duplo_hsm(
                        envio_individual=envio_individual,
                        envio_matrix=envio_matrix,
                        matriz_config=matrix_config,
                        template_hsm=template_a_usar,
                        variaveis_hsm=variaveis_hsm
                    )
                    
                    # Contabiliza resultados
                    if resultado_primeiro and resultado_primeiro['success']:
                        total_enviados += 1
                        if resultado_segundo and resultado_segundo['success']:
                            total_enviados += 1  # Segundo HSM também foi enviado
                            logger.info(f"✅ AMBOS HSMs enviados com sucesso para {cliente.codigo_cliente}")
                        else:
                            total_erros += 1  # Segundo HSM falhou
                            logger.warning(f"⚠️  Primeiro HSM OK, mas segundo HSM falhou para {cliente.codigo_cliente}")
                    else:
                        total_erros += 1  # Primeiro HSM falhou
                        logger.error(f"❌ Primeiro HSM falhou para {cliente.codigo_cliente}")
                
                else:
                    # ========= ENVIO SIMPLES (LÓGICA ORIGINAL) =========
                    # Verifica se é template de pagamento e chama função apropriada
                    if template_a_usar.tipo_template == 'pagamento':
                        # Valida configuração de pagamento antes de prosseguir
                        config_valida, erros_config = validar_configuracao_pagamento(envio_matrix)
                        if not config_valida:
                            logger.error(f"Configuração inválida para envio de pagamento: {erros_config}")
                            envio_individual.status = 'erro'
                            envio_individual.erro_detalhado = f"Configuração inválida: {', '.join(erros_config)}"
                            envio_individual.save()
                            total_erros += 1
                            continue
                        
                        # Prepara dados específicos do pagamento com debug
                        try:
                            print(f"\n🎯 PROCESSANDO CLIENTE PARA PAGAMENTO: {getattr(cliente, 'codigo_cliente', 'N/A')}")
                        except:
                            pass
                        
                        logger.info(f"=== PREPARANDO PAGAMENTO PARA CLIENTE {getattr(cliente, 'codigo_cliente', 'N/A')} ===")
                        dados_pagamento = debug_payload_pagamento(cliente, envio_matrix)
                        url_file = getattr(cliente, 'link_boleto', None) or ""
                        
                        try:
                            print(f"📄 URL do arquivo: {url_file}")
                            print(f"🏷️  Template HSM: {getattr(template_a_usar, 'hsm_id', 'N/A')}")
                            print(f"📊 Cod Conta: {getattr(matrix_config, 'cod_conta', 'N/A')}")
                        except:
                            pass
                        
                        logger.info(f"URL do arquivo: {url_file}")
                        logger.info(f"Template HSM: {getattr(template_a_usar, 'hsm_id', 'N/A')}")
                        logger.info(f"Cod Conta: {getattr(matrix_config, 'cod_conta', 'N/A')}")
                        
                        # Armazena dados de pagamento no envio individual
                        envio_individual.dados_pagamento = dados_pagamento
                        envio_individual.url_file = url_file
                        envio_individual.save()
                        
                        # Envia HSM de pagamento
                        resultado = enviar_hsm_pagamento_matrix_django(
                            matrix_config=matrix_config,
                            hsm_template=template_a_usar,
                            cliente=cliente,
                            variaveis_hsm=variaveis_hsm,
                            dados_pagamento=dados_pagamento,
                            url_file=url_file,
                            envio_matrix=envio_matrix,
                            envio_individual=envio_individual
                        )
                    else:
                        # Envia HSM tradicional
                        resultado = enviar_hsm_matrix_django(
                            matrix_config=matrix_config,
                            hsm_template=template_a_usar,
                            cliente=cliente,
                            variaveis_hsm=variaveis_hsm,
                            envio_matrix=envio_matrix,
                            envio_individual=envio_individual
                        )
                    
                    # Processa resultado do envio simples
                    if resultado['success']:
                        envio_individual.marcar_enviado(resultado.get('data'))
                        total_enviados += 1
                        logger.info(f"HSM enviado com sucesso para {cliente.codigo_cliente}")
                    else:
                        erro_msg = resultado.get('error', 'Erro desconhecido')
                        envio_individual.marcar_erro(erro_msg, resultado.get('data'))
                        total_erros += 1
                        logger.error(f"Erro ao enviar HSM para {cliente.codigo_cliente}: {erro_msg}")
                
            except Exception as e:
                erro_msg = f"Erro inesperado: {str(e)}"
                envio_individual.marcar_erro(erro_msg)
                total_erros += 1
                logger.error(f"Erro inesperado ao enviar HSM para {envio_individual.cliente.codigo_cliente}: {e}")
            
            # Delay entre envios
            time.sleep(1)
            
            # Atualiza progresso a cada 5 envios
            if (total_enviados + total_erros) % 5 == 0:
                envio_matrix.total_enviados = total_enviados
                envio_matrix.total_erros = total_erros
                envio_matrix.total_pendentes = total_clientes - total_enviados - total_erros
                envio_matrix.save()
        
        # Finaliza o envio
        envio_matrix.total_enviados = total_enviados
        envio_matrix.total_erros = total_erros
        envio_matrix.total_pendentes = total_clientes - total_enviados - total_erros
        
        if envio_matrix.status_envio != 'cancelado':
            status_final = 'concluido' if total_erros == 0 else 'concluido'
            log_final = f'Envio concluído. {total_enviados} enviados, {total_erros} erros.'
            envio_matrix.atualizar_status(status_final, log_final)
        
        logger.info(f"Processamento do envio HSM {envio_matrix_id} finalizado")
        
    except Exception as e:
        logger.error(f"Erro no processamento do envio HSM {envio_matrix_id}: {e}")
        try:
            envio_matrix = EnvioHSMMatrix.objects.get(id=envio_matrix_id)
            envio_matrix.atualizar_status('erro', f'Erro durante envio: {str(e)}')
        except:
            pass

def obter_ultimo_envio_hsm(execucao_id):
    """Obtém o último envio HSM de uma execução para reutilizar configurações"""
    try:
        ultimo_envio = EnvioHSMMatrix.objects.filter(
            consulta_execucao_id=execucao_id
        ).order_by('-data_criacao').first()
        
        if ultimo_envio:
            return {
                'matrix_config': ultimo_envio.matrix_api_config,
                'hsm_template': ultimo_envio.hsm_template,
                'hsm_template_contingencia': ultimo_envio.hsm_template_contingencia,
                'configuracao_variaveis': ultimo_envio.configuracao_variaveis,
                'configuracao_variaveis_contingencia': ultimo_envio.configuracao_variaveis_contingencia,
                # Campos do segundo HSM
                'habilitar_segundo_hsm': ultimo_envio.habilitar_segundo_hsm,
                'hsm_template_segundo': ultimo_envio.hsm_template_segundo,
                'configuracao_variaveis_segundo': ultimo_envio.configuracao_variaveis_segundo,
                'intervalo_segundo_hsm': ultimo_envio.intervalo_segundo_hsm,
                'razao_social_empresa_segundo': ultimo_envio.razao_social_empresa_segundo,
                'cnpj_empresa_segundo': ultimo_envio.cnpj_empresa_segundo,
                'nome_produto_padrao_segundo': ultimo_envio.nome_produto_padrao_segundo,
                'configuracao_pagamento_segundo': ultimo_envio.configuracao_pagamento_segundo
            }
    except Exception as e:
        logger.error(f"Erro ao obter último envio HSM da execução {execucao_id}: {e}")
    
    return None

@require_http_methods(["POST"])
def enviar_hsm_configuracao_atual(request, execucao_id):
    """Envia HSM usando as configurações do último envio da execução"""
    try:
        titulo = request.POST.get('titulo')
        
        if not titulo:
            return JsonResponse({
                'status': 'error',
                'message': 'Título do envio é obrigatório.'
            }, status=400)
        
        # Busca execução
        execucao = ConsultaExecucao.objects.get(id=execucao_id)
        
        # Verifica se a execução foi concluída com sucesso
        if execucao.status != 'concluida':
            return JsonResponse({
                'status': 'error',
                'message': 'Apenas execuções concluídas podem ter HSM enviado.'
            }, status=400)
        
        # Obtém configurações do último envio
        config_anterior = obter_ultimo_envio_hsm(execucao_id)
        
        if not config_anterior:
            return JsonResponse({
                'status': 'error',
                'message': 'Nenhum envio HSM anterior encontrado para esta execução. Use a configuração manual.'
            }, status=404)
        
        # Verifica se ainda há clientes válidos considerando se a API foi pulada
        if execucao.pular_consulta_api:
            # Se API foi pulada, considera todos os clientes da execução
            clientes_sucesso = ConsultaCliente.objects.filter(
                execucao=execucao
            ).count()
        else:
            # Se API foi consultada, considera apenas sucessos
            clientes_sucesso = ConsultaCliente.objects.filter(
                execucao=execucao, 
                sucesso_api=True
            ).count()
        
        if clientes_sucesso == 0:
            return JsonResponse({
                'status': 'error',
                'message': 'Nenhum cliente com dados válidos encontrado nesta execução.'
            }, status=400)
        
        # Cria novo envio HSM com as configurações anteriores
        envio_matrix = EnvioHSMMatrix.objects.create(
            titulo=titulo,
            hsm_template=config_anterior['hsm_template'],
            hsm_template_contingencia=config_anterior['hsm_template_contingencia'],
            matrix_api_config=config_anterior['matrix_config'],
            consulta_execucao=execucao,
            configuracao_variaveis=config_anterior['configuracao_variaveis'],
            configuracao_variaveis_contingencia=config_anterior['configuracao_variaveis_contingencia'],
            # Configurações do segundo HSM
            habilitar_segundo_hsm=config_anterior.get('habilitar_segundo_hsm', False),
            hsm_template_segundo=config_anterior.get('hsm_template_segundo'),
            configuracao_variaveis_segundo=config_anterior.get('configuracao_variaveis_segundo', {}),
            intervalo_segundo_hsm=config_anterior.get('intervalo_segundo_hsm', 3),
            razao_social_empresa_segundo=config_anterior.get('razao_social_empresa_segundo', ''),
            cnpj_empresa_segundo=config_anterior.get('cnpj_empresa_segundo', ''),
            nome_produto_padrao_segundo=config_anterior.get('nome_produto_padrao_segundo', ''),
            configuracao_pagamento_segundo=config_anterior.get('configuracao_pagamento_segundo', {}),
            status_envio='pendente'
        )
        
        # Inicia processamento em thread separada
        thread = threading.Thread(target=processar_envio_hsm_background, args=(envio_matrix.id,))
        thread.daemon = True
        thread.start()
        
        redirect_url = reverse('detalhe_envio_hsm', args=[envio_matrix.id])
        
        return JsonResponse({
            'status': 'success',
            'message': f'Envio HSM "{envio_matrix.titulo}" iniciado com as configurações anteriores!',
            'redirect_url': redirect_url
        })
        
    except ConsultaExecucao.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Execução não encontrada.'
        }, status=404)
    except Exception as e:
        logger.error(f"Erro ao iniciar envio HSM com configuração atual: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=500)

@require_http_methods(["POST"])
def iniciar_envio_hsm(request):
    """Inicia o envio de HSM para uma execução (padrão ou pagamento)"""
    try:
        titulo = request.POST.get('titulo')
        execucao_id = request.POST.get('execucao_id')
        hsm_template_id = request.POST.get('hsm_template')
        matrix_config_id = request.POST.get('matrix_config')
        
        # Validação básica
        if not all([titulo, execucao_id, hsm_template_id, matrix_config_id]):
            return JsonResponse({
                'status': 'error',
                'message': 'Todos os campos são obrigatórios.'
            }, status=400)
        
        # Busca objetos relacionados
        execucao = ConsultaExecucao.objects.get(id=execucao_id)
        hsm_template = HSMTemplate.objects.get(id=hsm_template_id)
        matrix_config = MatrixAPIConfig.objects.get(id=matrix_config_id)
        
        # Captura configuração das variáveis (mapeamento HSM -> Campo Cliente)
        configuracao_variaveis = {}
        variaveis_hsm = hsm_template.get_variaveis_descricao()
        
        for var_hsm in variaveis_hsm.keys():
            campo_mapeado = request.POST.get(f'var_mapping_{var_hsm}')
            if campo_mapeado:
                configuracao_variaveis[var_hsm] = campo_mapeado
        
        # Verifica se há template de contingência
        hsm_template_contingencia_id = request.POST.get('hsm_template_contingencia')
        hsm_template_contingencia = None
        configuracao_variaveis_contingencia = {}
        
        if hsm_template_contingencia_id:
            hsm_template_contingencia = HSMTemplate.objects.get(id=hsm_template_contingencia_id)
            variaveis_hsm_contingencia = hsm_template_contingencia.get_variaveis_descricao()
            
            for var_hsm in variaveis_hsm_contingencia.keys():
                campo_mapeado = request.POST.get(f'var_mapping_contingencia_{var_hsm}')
                if campo_mapeado:
                    configuracao_variaveis_contingencia[var_hsm] = campo_mapeado
        
        # Dados base para criação do envio
        envio_data = {
            'titulo': titulo,
            'hsm_template': hsm_template,
            'hsm_template_contingencia': hsm_template_contingencia,
            'matrix_api_config': matrix_config,
            'consulta_execucao': execucao,
            'configuracao_variaveis': configuracao_variaveis,
            'configuracao_variaveis_contingencia': configuracao_variaveis_contingencia,
            'status_envio': 'pendente'
        }
        
        # Se for template de pagamento, captura dados específicos
        if hsm_template.tipo_template == 'pagamento':
            # Verifica se foi selecionada uma configuração de pagamento
            configuracao_pagamento_hsm_id = request.POST.get('configuracao_pagamento_hsm')
            
            if configuracao_pagamento_hsm_id:
                # Usa configuração salva
                try:
                    configuracao_pagamento_hsm = ConfiguracaoPagamentoHSM.objects.get(id=configuracao_pagamento_hsm_id)
                    envio_data['configuracao_pagamento_hsm'] = configuracao_pagamento_hsm
                    
                    # Ainda preenche os campos diretos para compatibilidade
                    envio_data['razao_social_empresa'] = configuracao_pagamento_hsm.razao_social_empresa
                    envio_data['cnpj_empresa'] = configuracao_pagamento_hsm.cnpj_empresa
                    envio_data['nome_produto_padrao'] = configuracao_pagamento_hsm.nome_produto_padrao
                    
                except ConfiguracaoPagamentoHSM.DoesNotExist:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Configuração de pagamento selecionada não encontrada.'
                    }, status=404)
            else:
                # Configuração manual
                razao_social_empresa = request.POST.get('razao_social_empresa')
                cnpj_empresa = request.POST.get('cnpj_empresa')
                nome_produto_padrao = request.POST.get('nome_produto_padrao')
                
                # Validação adicional para pagamento
                if not all([razao_social_empresa, cnpj_empresa, nome_produto_padrao]):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Para templates de pagamento são obrigatórios: Razão Social, CNPJ e Nome do Produto.'
                    }, status=400)
                
                # Adiciona dados específicos de pagamento
                envio_data['razao_social_empresa'] = razao_social_empresa
                envio_data['cnpj_empresa'] = cnpj_empresa
                envio_data['nome_produto_padrao'] = nome_produto_padrao
                
                # Captura configurações opcionais de pagamento
                configuracao_pagamento = {}
                if request.POST.get('val_imposto'):
                    try:
                        configuracao_pagamento['val_imposto'] = float(request.POST.get('val_imposto', 0))
                    except ValueError:
                        configuracao_pagamento['val_imposto'] = 0
                if request.POST.get('val_desconto'):
                    try:
                        configuracao_pagamento['val_desconto'] = float(request.POST.get('val_desconto', 0))
                    except ValueError:
                        configuracao_pagamento['val_desconto'] = 0
                if request.POST.get('tipo_produto'):
                    configuracao_pagamento['tipo_produto'] = request.POST.get('tipo_produto')
                
                envio_data['configuracao_pagamento'] = configuracao_pagamento
        
        # ========= CONFIGURAÇÕES DO SEGUNDO HSM =========
        habilitar_segundo_hsm = request.POST.get('habilitar_segundo_hsm') == 'true'
        envio_data['habilitar_segundo_hsm'] = habilitar_segundo_hsm
        
        if habilitar_segundo_hsm:
            # Template do segundo HSM
            hsm_template_segundo_id = request.POST.get('hsm_template_segundo')
            if hsm_template_segundo_id:
                hsm_template_segundo = HSMTemplate.objects.get(id=hsm_template_segundo_id)
                envio_data['hsm_template_segundo'] = hsm_template_segundo
                
                # Captura configuração das variáveis do segundo HSM
                configuracao_variaveis_segundo = {}
                variaveis_hsm_segundo = hsm_template_segundo.get_variaveis_descricao()
                
                for var_hsm in variaveis_hsm_segundo.keys():
                    campo_mapeado = request.POST.get(f'var_mapping_segundo_{var_hsm}')
                    if campo_mapeado:
                        configuracao_variaveis_segundo[var_hsm] = campo_mapeado
                
                envio_data['configuracao_variaveis_segundo'] = configuracao_variaveis_segundo
                
                # Intervalo para o segundo HSM
                intervalo_segundo = request.POST.get('intervalo_segundo_hsm')
                try:
                    envio_data['intervalo_segundo_hsm'] = int(intervalo_segundo) if intervalo_segundo else 3
                except ValueError:
                    envio_data['intervalo_segundo_hsm'] = 3
                
                # Se o segundo HSM for de pagamento, captura configurações específicas
                if hsm_template_segundo.tipo_template == 'pagamento':
                    envio_data['razao_social_empresa_segundo'] = request.POST.get('razao_social_empresa_segundo', '')
                    envio_data['cnpj_empresa_segundo'] = request.POST.get('cnpj_empresa_segundo', '')
                    envio_data['nome_produto_padrao_segundo'] = request.POST.get('nome_produto_padrao_segundo', '')
                    
                    # Configurações opcionais de pagamento do segundo HSM
                    configuracao_pagamento_segundo = {}
                    if request.POST.get('val_imposto_segundo'):
                        try:
                            configuracao_pagamento_segundo['val_imposto'] = float(request.POST.get('val_imposto_segundo', 0))
                        except ValueError:
                            configuracao_pagamento_segundo['val_imposto'] = 0
                    if request.POST.get('val_desconto_segundo'):
                        try:
                            configuracao_pagamento_segundo['val_desconto'] = float(request.POST.get('val_desconto_segundo', 0))
                        except ValueError:
                            configuracao_pagamento_segundo['val_desconto'] = 0
                    if request.POST.get('tipo_produto_segundo'):
                        configuracao_pagamento_segundo['tipo_produto'] = request.POST.get('tipo_produto_segundo')
                    
                    envio_data['configuracao_pagamento_segundo'] = configuracao_pagamento_segundo
        
        # Cria novo envio HSM
        envio_matrix = EnvioHSMMatrix.objects.create(**envio_data)
        
        # Inicia processamento em thread separada
        thread = threading.Thread(target=processar_envio_hsm_background, args=(envio_matrix.id,))
        thread.daemon = True
        thread.start()
        
        redirect_url = reverse('detalhe_envio_hsm', args=[envio_matrix.id])
        
        tipo_msg = "Pagamento" if hsm_template.tipo_template == 'pagamento' else "Padrão"
        duplo_msg = " (DUPLO)" if habilitar_segundo_hsm else ""
        
        return JsonResponse({
            'status': 'success',
            'message': f'Envio HSM {tipo_msg}{duplo_msg} "{envio_matrix.titulo}" iniciado com sucesso!',
            'redirect_url': redirect_url
        })
        
    except Exception as e:
        logger.error(f"Erro ao iniciar envio HSM: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=500)

@require_http_methods(["POST"])
def reiniciar_envio_hsm(request):
    """Reinicia o envio de HSM apenas para clientes pendentes"""
    try:
        envio_id = request.POST.get('envio_id')
        
        if not envio_id:
            return JsonResponse({
                'status': 'error',
                'message': 'ID do envio é obrigatório.'
            }, status=400)
        
        # Busca o envio
        envio_matrix = EnvioHSMMatrix.objects.get(id=envio_id)
        
        # Verifica se há clientes pendentes
        clientes_pendentes = EnvioHSMIndividual.objects.filter(
            envio_matrix=envio_matrix,
            status='pendente'
        ).count()
        
        if clientes_pendentes == 0:
            return JsonResponse({
                'status': 'error',
                'message': 'Não há clientes pendentes para reenvio.'
            }, status=400)
        
        # Atualiza status do envio principal para pendente novamente
        envio_matrix.status_envio = 'pendente'
        envio_matrix.save()
        
        # Inicia processamento em thread separada apenas para pendentes
        thread = threading.Thread(target=processar_envio_hsm_background, args=(envio_matrix.id, True))
        thread.daemon = True
        thread.start()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Reenvio iniciado para {clientes_pendentes} clientes pendentes!'
        })
        
    except EnvioHSMMatrix.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Envio não encontrado.'
        }, status=404)
        
    except Exception as e:
        logger.error(f"Erro ao reiniciar envio HSM: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro interno: {str(e)}'
        }, status=500)


def listar_envios_hsm(request):
    """Lista todos os envios HSM"""
    envios = EnvioHSMMatrix.objects.select_related(
        'hsm_template',
        'matrix_api_config', 
        'consulta_execucao'
    ).all().order_by('-data_criacao')
    
    # Filtros opcionais
    status_filter = request.GET.get('status')
    if status_filter:
        envios = envios.filter(status_envio=status_filter)
    
    paginator = Paginator(envios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'campanhas/listar_envios_hsm.html', {'page_obj': page_obj})

def detalhe_envio_hsm(request, envio_id):
    """Mostra detalhes de um envio HSM específico"""
    envio = get_object_or_404(EnvioHSMMatrix, id=envio_id)
    envios_individuais = EnvioHSMIndividual.objects.filter(envio_matrix=envio).order_by('-data_envio')
    
    # Paginação dos envios individuais
    paginator = Paginator(envios_individuais, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'envio': envio,
        'page_obj': page_obj,
        'total_envios': envios_individuais.count()
    }
    
    return render(request, 'campanhas/detalhe_envio_hsm.html', context)

def status_envio_hsm_ajax(request, envio_id):
    """Retorna o status atual de um envio HSM via AJAX"""
    try:
        envio = EnvioHSMMatrix.objects.get(id=envio_id)
        return JsonResponse({
            'status': envio.status_envio,
            'total_clientes': envio.total_clientes,
            'total_enviados': envio.total_enviados,
            'total_erros': envio.total_erros,
            'total_pendentes': envio.total_pendentes,
            'progresso_percentual': envio.get_progresso_percentual(),
            'log_execucao': envio.log_execucao or '',
            'data_fim_envio': envio.data_fim_envio.isoformat() if envio.data_fim_envio else None
        })
    except EnvioHSMMatrix.DoesNotExist:
        return JsonResponse({'error': 'Envio não encontrado'}, status=404)

@require_http_methods(["POST"])
def cancelar_envio_hsm(request, envio_id):
    """Cancela um envio HSM em andamento"""
    try:
        envio = EnvioHSMMatrix.objects.get(id=envio_id)
        
        if envio.status_envio not in ['pendente', 'enviando']:
            return JsonResponse({
                'status': 'error',
                'message': 'Apenas envios pendentes ou em andamento podem ser cancelados.'
            }, status=400)
        
        envio.atualizar_status('cancelado', 'Envio cancelado pelo usuário')
        
        # Cancela envios individuais pendentes
        EnvioHSMIndividual.objects.filter(
            envio_matrix=envio,
            status='pendente'
        ).update(status='cancelado')
        
        logger.info(f"Envio HSM {envio_id} cancelado pelo usuário")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Envio cancelado com sucesso.'
        })
        
    except EnvioHSMMatrix.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Envio não encontrado.'
        }, status=404)
    except Exception as e:
        logger.error(f"Erro ao cancelar envio HSM {envio_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'Erro ao cancelar envio: {str(e)}'
        }, status=500)

def criar_template_hsm_dinamico(request, cliente_id):
    """
    Cria um template HSM dinâmico baseado nos dados disponíveis do cliente
    """
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)
    
    try:
        cliente = ClienteConsultado.objects.get(id=cliente_id)
        template_personalizado = request.POST.get('template', '')
        
        from .utils import criar_template_hsm_com_dados_dinamicos
        
        if template_personalizado:
            # Usa template personalizado fornecido pelo usuário
            template_final = criar_template_hsm_com_dados_dinamicos(cliente, template_personalizado)
        else:
            # Usa template padrão com dados dinâmicos
            template_final = criar_template_hsm_com_dados_dinamicos(cliente)
        
        # Obtém dados disponíveis para referência
        dados_disponiveis = cliente.get_dados_completos()
        dados_dinamicos = cliente.get_todos_dados_dinamicos()
        
        return JsonResponse({
            'cliente': {
                'id': cliente.id,
                'nome': cliente.nome_razaosocial,
                'codigo': cliente.codigo_cliente
            },
            'template_final': template_final,
            'dados_disponiveis': dados_disponiveis,
            'dados_dinamicos': dados_dinamicos,
            'total_dados_dinamicos': len(dados_dinamicos),
            'campos_disponiveis': list(dados_disponiveis.keys())
        })
        
    except ClienteConsultado.DoesNotExist:
        return JsonResponse({'erro': 'Cliente não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'erro': f'Erro ao criar template: {str(e)}'}, status=500)

def analisar_template_sql(request, template_id):
    """
    Analisa um template SQL e identifica possíveis campos dinâmicos
    """
    try:
        template = TemplateSQL.objects.get(id=template_id)
        
        from .utils import mapear_campos_sql_para_dinamicos, validar_template_sql_variaveis
        
        # Analisa campos possíveis
        campos_identificados = mapear_campos_sql_para_dinamicos(template.consulta_sql)
        
        # Extrai variáveis do template
        variaveis_encontradas = template.extrair_variaveis_do_sql()
        
        # Valida se o template tem variáveis configuradas
        variaveis_configuradas = template.variaveis_config or {}
        
        return JsonResponse({
            'template': {
                'id': template.id,
                'titulo': template.titulo,
                'descricao': template.descricao
            },
            'analise_sql': {
                'campos_identificados': campos_identificados,
                'variaveis_encontradas': variaveis_encontradas,
                'variaveis_configuradas': variaveis_configuradas,
                'total_variaveis': len(variaveis_encontradas),
                'total_configuradas': len(variaveis_configuradas)
            },
            'sql_preview': template.consulta_sql[:500] + '...' if len(template.consulta_sql) > 500 else template.consulta_sql
        })
        
    except TemplateSQL.DoesNotExist:
        return JsonResponse({'erro': 'Template SQL não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'erro': f'Erro ao analisar template: {str(e)}'}, status=500)

def listar_variaveis_cliente_api(request, cliente_id):
    """
    API para listar todas as variáveis disponíveis de um cliente
    Útil para mostrar quais campos estão disponíveis para HSM e Flow
    """
    try:
        cliente = ClienteConsultado.objects.get(id=cliente_id)
        
        # Usa a função utilitária para obter todas as variáveis
        variaveis = listar_variaveis_disponiveis_cliente(cliente)
        
        # Cria resumo para interface
        resumo = {
            'cliente': {
                'id': cliente.id,
                'codigo': cliente.codigo_cliente,
                'nome': cliente.nome_razaosocial,
                'empresa': cliente.credencial_banco.titulo if cliente.credencial_banco else None
            },
            'total_campos_fixos': len(variaveis['campos_fixos']),
            'total_campos_dinamicos': len(variaveis['campos_dinamicos']),
            'total_metadados': len(variaveis['metadados']),
            'total_geral': len(variaveis['campos_fixos']) + len(variaveis['campos_dinamicos']) + len(variaveis['metadados'])
        }
        
        # Lista todas as variáveis para HSM (com exemplos)
        variaveis_hsm_exemplos = {}
        for categoria, campos in variaveis.items():
            for nome, info in campos.items():
                if categoria == 'campos_dinamicos':
                    # Para campos dinâmicos, mostra as duas opções
                    variaveis_hsm_exemplos[info['nome_hsm']] = {
                        'valor': info['valor'],
                        'descricao': info['descricao'],
                        'categoria': 'dinâmico',
                        'exemplo_uso': f"{{{{ {info['nome_hsm']} }}}}"
                    }
                    variaveis_hsm_exemplos[nome] = {
                        'valor': info['valor'],
                        'descricao': f"{info['descricao']} (nome direto)",
                        'categoria': 'dinâmico',
                        'exemplo_uso': f"{{{{ {nome} }}}}"
                    }
                else:
                    variaveis_hsm_exemplos[nome] = {
                        'valor': info['valor'],
                        'descricao': info['descricao'],
                        'categoria': categoria.replace('_', ' '),
                        'exemplo_uso': f"{{{{ {nome} }}}}"
                    }
        
        return JsonResponse({
            'status': 'success',
            'resumo': resumo,
            'variaveis_organizadas': variaveis,
            'variaveis_hsm_completas': variaveis_hsm_exemplos,
            'exemplos_uso': {
                'hsm_template': """Olá {{nome_cliente}}!
                
Sua fatura {{id_fatura}} está disponível.
Valor: R$ {{valor_fatura}}
Vencimento: {{vencimento_fatura}}

{% if campos_dinamicos %}
Dados adicionais:
{% for campo in campos_dinamicos %}
{{campo.nome}}: {{campo.valor}}
{% endfor %}
{% endif %}

Formas de pagamento:
PIX: {{pix_copia_cola}}
Boleto: {{link_boleto}}""",
                'flow_variaveis': 'Todas as variáveis são automaticamente enviadas para o flow_variaveis'
            }
        })
        
    except ClienteConsultado.DoesNotExist:
        return JsonResponse({'erro': 'Cliente não encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'erro': f'Erro ao listar variáveis: {str(e)}'}, status=500)