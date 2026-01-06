

def extrair_dados_dinamicos_sql(cliente_data: dict, dados_api: dict = None) -> dict:
    """
    Extrai dados dinâmicos dos templates SQL executados
    Identifica automaticamente campos que não são padrão e os retorna
    
    Args:
        cliente_data: Dados retornados da consulta SQL
        dados_api: Dados retornados da API (opcional)
    
    Returns:
        Dicionário com dados dinâmicos extraídos
    """
    # Campos fixos que já existem no modelo ClienteConsultado (nomes do modelo Django)
    campos_fixos = {
        'codigo_cliente', 'nome_razaosocial', 'telefone_corrigido', 
        'id_fatura', 'vencimento_fatura', 'valor_fatura', 'pix', 
        'codigo_barras', 'link_boleto', 'dados_dinamicos', 'credencial_banco',
        'data_criacao', 'data_atualizacao'
    }
    
    # Também considera campos SQL que são mapeados para campos fixos
    campos_sql_mapeados = {
        'TelefoneCorrigido', 'telefonecorrigido',  # Ambas as versões do telefone
        'data_vencimento', 'valor', 'pix_copia_cola', 
        'linha_digitavel', 'link'
    }
    
    dados_dinamicos = {}
    
    # Processa dados do template SQL
    if cliente_data:
        for chave, valor in cliente_data.items():
            # Ignora se é campo fixo (modelo Django) ou campo SQL mapeado
            if (chave not in campos_fixos and 
                chave not in campos_sql_mapeados and
                valor is not None and 
                valor != '' and
                not chave.startswith('_')):
                dados_dinamicos[chave] = valor
    
    # Processa dados da API
    if dados_api:
        for chave, valor in dados_api.items():
            # Ignora se é campo fixo (modelo Django) ou campo SQL mapeado
            if (chave not in campos_fixos and 
                chave not in campos_sql_mapeados and
                valor is not None and 
                valor != '' and
                not chave.startswith('_')):
                dados_dinamicos[chave] = valor
    
    return dados_dinamicos

def mapear_campos_sql_para_dinamicos(template_sql: str) -> dict:
    """
    Analisa um template SQL e identifica possíveis campos dinâmicos
    Útil para planejamento e documentação
    
    Args:
        template_sql: String contendo o SQL do template
    
    Returns:
        Dicionário com campos identificados e suas descrições
    """
    import re
    
    # Padrões comuns em consultas SQL
    padroes_campos = {
        'endereco': r'\b(endereco|endereço|logradouro|bairro|cidade|estado|cep)\b',
        'contato': r'\b(email|telefone|celular|whatsapp|contato)\b',
        'financeiro': r'\b(saldo|limite|credito|debito|historico|parcela)\b',
        'pessoal': r'\b(cpf|cnpj|rg|data_nascimento|idade|genero)\b',
        'comercial': r'\b(plano|servico|contrato|adesao|cancelamento)\b',
        'geografico': r'\b(regiao|zona|cobertura|distancia)\b'
    }
    
    campos_identificados = {}
    
    for categoria, padrao in padroes_campos.items():
        matches = re.findall(padrao, template_sql, re.IGNORECASE)
        if matches:
            campos_identificados[categoria] = list(set(matches))
    
    return campos_identificados

def validar_template_sql_variaveis(template_sql: str, variaveis_necessarias: list) -> dict:
    """
    Valida se um template SQL contém todas as variáveis necessárias
    
    Args:
        template_sql: SQL do template
        variaveis_necessarias: Lista de variáveis que devem estar presentes
    
    Returns:
        Dicionário com resultado da validação
    """
    import re
    
    # Extrai variáveis do template (formato {{variavel}})
    padrao_variaveis = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}'
    variaveis_encontradas = re.findall(padrao_variaveis, template_sql)
    
    # Verifica quais variáveis necessárias estão presentes
    variaveis_presentes = [var for var in variaveis_necessarias if var in variaveis_encontradas]
    variaveis_faltantes = [var for var in variaveis_necessarias if var not in variaveis_encontradas]
    
    return {
        'valido': len(variaveis_faltantes) == 0,
        'variaveis_presentes': variaveis_presentes,
        'variaveis_faltantes': variaveis_faltantes,
        'total_necessarias': len(variaveis_necessarias),
        'total_presentes': len(variaveis_presentes),
        'variaveis_extra': [var for var in variaveis_encontradas if var not in variaveis_necessarias]
    }

def criar_template_hsm_com_dados_dinamicos(cliente, template_base: str = None) -> str:
    """
    Cria um template HSM usando dados dinâmicos disponíveis
    
    Args:
        cliente: Instância do ClienteConsultado
        template_base: Template base (opcional)
    
    Returns:
        Template HSM com variáveis disponíveis
    """
    if not template_base:
        template_base = """Olá {{nome_razaosocial}}!

📋 **Dados da Fatura:**
🏷️ ID: {{id_fatura}}
💰 Valor: {{valor_fatura_formatado}}
📅 Vencimento: {{vencimento_fatura_formatado}}

💳 **Formas de Pagamento:**
{{#pix}}📱 PIX: {{pix}}{{/pix}}
{{#codigo_barras}}📊 Código de Barras: {{codigo_barras}}{{/codigo_barras}}
{{#link_boleto}}🔗 Boleto: {{link_boleto}}{{/link_boleto}}

🏢 **Empresa:** {{empresa}}

{{#dados_dinamicos}}📊 **Informações Adicionais:**
{{#each dados_dinamicos}}
• {{@key}}: {{this}}
{{/each}}{{/dados_dinamicos}}

Precisa de ajuda? Entre em contato conosco!"""
    
    # Substitui variáveis básicas
    dados = cliente.get_dados_completos()
    
    for chave, valor in dados.items():
        if valor is not None:
            placeholder = f"{{{{{chave}}}}}"
            if isinstance(valor, (int, float)):
                template_base = template_base.replace(placeholder, str(valor))
            else:
                template_base = template_base.replace(placeholder, str(valor) if valor else '')
    
    return template_base

def exportar_dados_cliente_json(cliente) -> str:
    """
    Exporta todos os dados do cliente em formato JSON
    Útil para integração com sistemas externos
    
    Args:
        cliente: Instância do ClienteConsultado
    
    Returns:
        String JSON com todos os dados
    """
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    
    dados_completos = cliente.get_dados_completos()
    
    # Converte datas para formato ISO
    for chave, valor in dados_completos.items():
        if hasattr(valor, 'isoformat'):
            dados_completos[chave] = valor.isoformat()
    
    return json.dumps(dados_completos, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)
