"""
Serviços para importação e processamento de CSVs de leads
"""

import csv
import io
import re
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import BaseLeads, Lead
import logging

logger = logging.getLogger(__name__)


class ServicoImportacaoCSV:
    """
    Serviço para importar e processar arquivos CSV de leads
    """
    
    # Delimitadores suportados
    DELIMITADORES = [';', ',', '\t', '|']
    
    # Encodings suportados
    ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
    
    def __init__(self):
        self.arquivo = None
        self.conteudo = None
        self.encoding_detectado = None
        self.delimitador_detectado = None
    
    @staticmethod
    def validar_email(email):
        """
        Valida formato de email
        
        Args:
            email: string com email a validar
        
        Returns:
            bool: True se válido, False caso contrário
        """
        if not email or not isinstance(email, str):
            return False
        
        # Remover espaços
        email = email.strip()
        
        # Pattern básico de validação
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        return bool(re.match(pattern, email))
    
    def detectar_encoding(self, arquivo_bytes):
        """
        Tenta detectar o encoding do arquivo
        
        Args:
            arquivo_bytes: bytes do arquivo
        
        Returns:
            str: encoding detectado
        """
        for encoding in self.ENCODINGS:
            try:
                arquivo_bytes.decode(encoding)
                logger.info(f"Encoding detectado: {encoding}")
                return encoding
            except (UnicodeDecodeError, AttributeError):
                continue
        
        # Fallback para UTF-8
        logger.warning("Não foi possível detectar encoding, usando UTF-8")
        return 'utf-8'
    
    def detectar_delimitador(self, conteudo_str, max_linhas=5):
        """
        Detecta o delimitador usado no CSV
        
        Args:
            conteudo_str: string com conteúdo do CSV
            max_linhas: número de linhas a analisar
        
        Returns:
            str: delimitador detectado
        """
        linhas = conteudo_str.split('\n')[:max_linhas]
        
        # Contar ocorrências de cada delimitador
        contagens = {}
        for delimitador in self.DELIMITADORES:
            contagens[delimitador] = sum(linha.count(delimitador) for linha in linhas)
        
        # Retornar o mais frequente
        delimitador_detectado = max(contagens, key=contagens.get)
        
        logger.info(f"Delimitador detectado: '{delimitador_detectado}' (contagens: {contagens})")
        return delimitador_detectado
    
    def ler_arquivo(self, arquivo):
        """
        Lê o arquivo CSV e detecta encoding/delimitador
        
        Args:
            arquivo: arquivo upload do Django (InMemoryUploadedFile ou TemporaryUploadedFile)
        
        Returns:
            tuple: (conteudo_str, encoding, delimitador)
        """
        # Ler bytes do arquivo
        arquivo.seek(0)
        arquivo_bytes = arquivo.read()
        
        # Detectar encoding
        encoding = self.detectar_encoding(arquivo_bytes)
        
        # Decodificar
        try:
            conteudo_str = arquivo_bytes.decode(encoding)
        except Exception as e:
            logger.error(f"Erro ao decodificar arquivo: {str(e)}")
            # Tentar UTF-8 ignorando erros
            conteudo_str = arquivo_bytes.decode('utf-8', errors='ignore')
            encoding = 'utf-8'
        
        # Detectar delimitador
        delimitador = self.detectar_delimitador(conteudo_str)
        
        return conteudo_str, encoding, delimitador
    
    def extrair_colunas(self, conteudo_str, delimitador):
        """
        Extrai as colunas (cabeçalho) do CSV
        
        Args:
            conteudo_str: string com conteúdo do CSV
            delimitador: delimitador a usar
        
        Returns:
            list: lista de nomes de colunas
        """
        # Ler como CSV
        reader = csv.DictReader(io.StringIO(conteudo_str), delimiter=delimitador)
        
        # Obter fieldnames (colunas)
        colunas = reader.fieldnames or []
        
        # Limpar nomes das colunas (remover espaços, BOM, etc)
        colunas_limpas = []
        for coluna in colunas:
            # Remover BOM, espaços, etc
            coluna_limpa = coluna.strip().replace('\ufeff', '')
            colunas_limpas.append(coluna_limpa)
        
        logger.info(f"Colunas extraídas: {colunas_limpas}")
        return colunas_limpas
    
    def obter_preview_dados(self, conteudo_str, delimitador, limite=10):
        """
        Obtém preview das primeiras linhas do CSV
        
        Args:
            conteudo_str: string com conteúdo do CSV
            delimitador: delimitador a usar
            limite: número de linhas a retornar
        
        Returns:
            list: lista de dicionários com dados das linhas
        """
        reader = csv.DictReader(io.StringIO(conteudo_str), delimiter=delimitador)
        
        preview = []
        for i, linha in enumerate(reader):
            if i >= limite:
                break
            
            # Limpar chaves do dicionário (remover BOM, espaços)
            linha_limpa = {}
            for chave, valor in linha.items():
                chave_limpa = chave.strip().replace('\ufeff', '')
                valor_limpo = valor.strip() if valor else ''
                linha_limpa[chave_limpa] = valor_limpo
            
            preview.append(linha_limpa)
        
        return preview
    
    def normalizar_nome_coluna(self, nome_coluna):
        """
        Normaliza nome de coluna para uso como variável em template
        Remove acentos, espaços, caracteres especiais
        
        Args:
            nome_coluna: nome original da coluna
        
        Returns:
            str: nome normalizado
        """
        import unicodedata
        
        # Remover acentos
        sem_acento = ''.join(
            c for c in unicodedata.normalize('NFD', nome_coluna)
            if unicodedata.category(c) != 'Mn'
        )
        
        # Substituir espaços e caracteres especiais por underscore
        normalizado = re.sub(r'[^a-zA-Z0-9_]', '_', sem_acento)
        
        # Remover underscores múltiplos
        normalizado = re.sub(r'_+', '_', normalizado)
        
        # Remover underscore no início/fim
        normalizado = normalizado.strip('_')
        
        # Garantir que não comece com número
        if normalizado and normalizado[0].isdigit():
            normalizado = 'col_' + normalizado
        
        return normalizado or 'coluna'
    
    def importar_leads(self, arquivo, nome_base, coluna_email, coluna_nome, descricao=''):
        """
        Importa leads de um arquivo CSV
        
        Args:
            arquivo: arquivo upload do Django
            nome_base: nome para a base de leads
            coluna_email: nome da coluna que contém email
            coluna_nome: nome da coluna que contém nome
            descricao: descrição da base (opcional)
        
        Returns:
            tuple: (base_leads, total_importados, total_invalidos, erros)
        """
        try:
            # 1. Ler e detectar encoding/delimitador
            conteudo_str, encoding, delimitador = self.ler_arquivo(arquivo)
            
            # 2. Extrair colunas
            colunas = self.extrair_colunas(conteudo_str, delimitador)
            
            # 3. Validar que colunas de email e nome existem
            if coluna_email not in colunas:
                raise ValidationError(f"Coluna '{coluna_email}' não encontrada no CSV")
            
            if coluna_nome not in colunas:
                raise ValidationError(f"Coluna '{coluna_nome}' não encontrada no CSV")
            
            # 4. Criar BaseLeads
            with transaction.atomic():
                base_leads = BaseLeads.objects.create(
                    nome=nome_base,
                    descricao=descricao,
                    arquivo_original_nome=arquivo.name,
                    colunas_disponiveis=colunas,
                    coluna_email=coluna_email,
                    coluna_nome=coluna_nome,
                    delimitador_usado=delimitador,
                    encoding_usado=encoding
                )
                
                # 5. Processar linhas do CSV
                reader = csv.DictReader(io.StringIO(conteudo_str), delimiter=delimitador)
                
                total_processados = 0
                total_validos = 0
                total_invalidos = 0
                erros = []
                emails_vistos = set()  # Para detectar duplicatas
                
                for i, linha in enumerate(reader, start=2):  # Começa em 2 (linha 1 é cabeçalho)
                    try:
                        # Limpar chaves do dicionário
                        linha_limpa = {}
                        for chave, valor in linha.items():
                            chave_limpa = chave.strip().replace('\ufeff', '')
                            valor_limpo = valor.strip() if valor else ''
                            linha_limpa[chave_limpa] = valor_limpo
                        
                        # Extrair email e nome
                        email = linha_limpa.get(coluna_email, '').strip()
                        nome = linha_limpa.get(coluna_nome, '').strip()
                        
                        # Validar email
                        if not email:
                            total_invalidos += 1
                            erros.append(f"Linha {i}: Email vazio")
                            continue
                        
                        if not self.validar_email(email):
                            total_invalidos += 1
                            Lead.objects.create(
                                base_leads=base_leads,
                                email=email,
                                nome=nome or 'Sem nome',
                                dados_adicionais={},
                                linha_original=i,
                                valido=False,
                                motivo_invalido=f"Email inválido: {email}"
                            )
                            erros.append(f"Linha {i}: Email inválido '{email}'")
                            continue
                        
                        # Verificar duplicata
                        email_lower = email.lower()
                        if email_lower in emails_vistos:
                            total_invalidos += 1
                            erros.append(f"Linha {i}: Email duplicado '{email}'")
                            continue
                        
                        emails_vistos.add(email_lower)
                        
                        # Validar nome
                        if not nome:
                            nome = email.split('@')[0]  # Usar parte do email como nome
                        
                        # Preparar dados adicionais (todas as outras colunas)
                        dados_adicionais = {}
                        for chave, valor in linha_limpa.items():
                            if chave not in [coluna_email, coluna_nome] and valor:
                                # Normalizar nome da chave para uso em template
                                chave_normalizada = self.normalizar_nome_coluna(chave)
                                dados_adicionais[chave] = valor
                                # Também adicionar versão normalizada
                                if chave_normalizada != chave:
                                    dados_adicionais[chave_normalizada] = valor
                        
                        # Criar lead
                        Lead.objects.create(
                            base_leads=base_leads,
                            email=email,
                            nome=nome,
                            dados_adicionais=dados_adicionais,
                            linha_original=i,
                            valido=True,
                            motivo_invalido=''
                        )
                        
                        total_validos += 1
                        total_processados += 1
                        
                    except Exception as e:
                        total_invalidos += 1
                        erro_msg = f"Linha {i}: Erro ao processar - {str(e)}"
                        erros.append(erro_msg)
                        logger.error(erro_msg)
                
                # 6. Atualizar totais da base
                base_leads.total_leads = total_processados + total_invalidos
                base_leads.total_validos = total_validos
                base_leads.total_invalidos = total_invalidos
                base_leads.save()
                
                logger.info(f"Importação concluída: {total_validos} válidos, {total_invalidos} inválidos")
                
                return base_leads, total_validos, total_invalidos, erros
                
        except Exception as e:
            logger.error(f"Erro ao importar CSV: {str(e)}")
            raise ValidationError(f"Erro ao importar arquivo CSV: {str(e)}")
    
    def identificar_coluna_email(self, colunas):
        """
        Tenta identificar automaticamente qual coluna contém email
        
        Args:
            colunas: lista de nomes de colunas
        
        Returns:
            str: nome da coluna de email ou None
        """
        palavras_email = ['email', 'e-mail', 'e_mail', 'mail', 'correo']
        
        for coluna in colunas:
            coluna_lower = coluna.lower().strip()
            if any(palavra in coluna_lower for palavra in palavras_email):
                return coluna
        
        return None
    
    def identificar_coluna_nome(self, colunas):
        """
        Tenta identificar automaticamente qual coluna contém nome
        
        Args:
            colunas: lista de nomes de colunas
        
        Returns:
            str: nome da coluna de nome ou None
        """
        palavras_nome = ['nome', 'name', 'razao', 'razão', 'cliente', 'contato', 'pessoa']
        
        for coluna in colunas:
            coluna_lower = coluna.lower().strip()
            if any(palavra in coluna_lower for palavra in palavras_nome):
                return coluna
        
        return None
    
    def validar_csv(self, arquivo, coluna_email, coluna_nome):
        """
        Valida o CSV antes de importar
        
        Args:
            arquivo: arquivo upload do Django
            coluna_email: nome da coluna de email
            coluna_nome: nome da coluna de nome
        
        Returns:
            dict: resultado da validação com erros/avisos
        """
        resultado = {
            'valido': True,
            'erros': [],
            'avisos': [],
            'total_linhas': 0,
            'preview_validos': 0,
            'preview_invalidos': 0
        }
        
        try:
            conteudo_str, encoding, delimitador = self.ler_arquivo(arquivo)
            colunas = self.extrair_colunas(conteudo_str, delimitador)
            
            # Validar colunas obrigatórias
            if coluna_email not in colunas:
                resultado['valido'] = False
                resultado['erros'].append(f"Coluna '{coluna_email}' não encontrada")
            
            if coluna_nome not in colunas:
                resultado['valido'] = False
                resultado['erros'].append(f"Coluna '{coluna_nome}' não encontrada")
            
            if not resultado['valido']:
                return resultado
            
            # Validar primeiras 100 linhas para preview
            reader = csv.DictReader(io.StringIO(conteudo_str), delimiter=delimitador)
            
            emails_preview = set()
            for i, linha in enumerate(reader, start=2):
                resultado['total_linhas'] += 1
                
                if i <= 101:  # Preview das primeiras 100 linhas
                    # Limpar chaves
                    linha_limpa = {}
                    for chave, valor in linha.items():
                        chave_limpa = chave.strip().replace('\ufeff', '')
                        linha_limpa[chave_limpa] = valor
                    
                    email = linha_limpa.get(coluna_email, '').strip()
                    
                    if not email:
                        resultado['preview_invalidos'] += 1
                        resultado['avisos'].append(f"Linha {i}: Email vazio")
                    elif not self.validar_email(email):
                        resultado['preview_invalidos'] += 1
                        resultado['avisos'].append(f"Linha {i}: Email inválido '{email}'")
                    elif email.lower() in emails_preview:
                        resultado['preview_invalidos'] += 1
                        resultado['avisos'].append(f"Linha {i}: Email duplicado '{email}'")
                    else:
                        resultado['preview_validos'] += 1
                        emails_preview.add(email.lower())
            
            # Limitar avisos a 10
            if len(resultado['avisos']) > 10:
                extras = len(resultado['avisos']) - 10
                resultado['avisos'] = resultado['avisos'][:10]
                resultado['avisos'].append(f"... e mais {extras} avisos")
            
            return resultado
            
        except Exception as e:
            resultado['valido'] = False
            resultado['erros'].append(f"Erro ao validar CSV: {str(e)}")
            return resultado
    
    def obter_sugestoes_colunas(self, arquivo):
        """
        Analisa o CSV e retorna sugestões de quais colunas usar para email e nome
        
        Args:
            arquivo: arquivo upload do Django
        
        Returns:
            dict: {'colunas': [...], 'sugestao_email': '...', 'sugestao_nome': '...', 'preview': [...]}
        """
        try:
            conteudo_str, encoding, delimitador = self.ler_arquivo(arquivo)
            colunas = self.extrair_colunas(conteudo_str, delimitador)
            
            # Identificar sugestões
            sugestao_email = self.identificar_coluna_email(colunas)
            sugestao_nome = self.identificar_coluna_nome(colunas)
            
            # Obter preview
            preview = self.obter_preview_dados(conteudo_str, delimitador, limite=5)
            
            return {
                'colunas': colunas,
                'sugestao_email': sugestao_email,
                'sugestao_nome': sugestao_nome,
                'preview': preview,
                'encoding': encoding,
                'delimitador': delimitador,
                'total_linhas_preview': len(preview)
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter sugestões de colunas: {str(e)}")
            raise ValidationError(f"Erro ao processar arquivo: {str(e)}")


def importar_leads_de_csv(arquivo, nome_base, coluna_email, coluna_nome, descricao=''):
    """
    Função utilitária para importar leads de CSV
    
    Args:
        arquivo: arquivo upload do Django
        nome_base: nome para a base de leads
        coluna_email: nome da coluna de email
        coluna_nome: nome da coluna de nome
        descricao: descrição da base
    
    Returns:
        BaseLeads: objeto da base criada
    """
    servico = ServicoImportacaoCSV()
    base_leads, total_validos, total_invalidos, erros = servico.importar_leads(
        arquivo, nome_base, coluna_email, coluna_nome, descricao
    )
    
    return base_leads


def validar_csv_leads(arquivo, coluna_email, coluna_nome):
    """
    Função utilitária para validar CSV antes de importar
    
    Args:
        arquivo: arquivo upload do Django
        coluna_email: nome da coluna de email
        coluna_nome: nome da coluna de nome
    
    Returns:
        dict: resultado da validação
    """
    servico = ServicoImportacaoCSV()
    return servico.validar_csv(arquivo, coluna_email, coluna_nome)
